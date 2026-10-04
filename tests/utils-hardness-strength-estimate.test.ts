import assert from "node:assert/strict";
import test from "node:test";
import {
  AT_PCT_HARDNESS_UNAVAILABLE_NOTE,
  HYPOEUTECTOID_C_MAX_WT_PCT,
  PAVLINA_VAN_TYNE_2008,
  SPECIMEN_HARDNESS_NOT_LOADED_NOTE,
  estimateSpecimenHardnessHV,
  estimateSteelHvFromYield,
  lowAlloyScopeViolation,
} from "../src/utils/hardnessStrengthEstimate";
import {
  MATERIAL_PRESETS,
  deriveProperties,
  migrateMaterialStoreState,
  useMaterialStore,
  withHardnessEstimate,
  type MaterialSpecimen,
} from "../src/store/useMaterialStore";
import { deriveSpecimenProperties, useMaterialSpecimenStore } from "../src/store/useMaterialSpecimenStore";
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

// A 4140-type low-alloy steel composition (wt%) inside the regression's data-set scope.
const LOW_ALLOY_4140 = { Fe: 97.2, C: 0.4, Mn: 0.9, Cr: 1.0, Mo: 0.2, Si: 0.25 };
const steel = { materialClass: "non-austenitic-steel" as const, composition: LOW_ALLOY_4140 };
const withC = (C: number | undefined) => ({ materialClass: "non-austenitic-steel" as const, composition: { Fe: 98.5, Mn: 0.8, C } as Record<string, number> });

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
  assert.equal(estimateSteelHvFromYield(951, steel).hv, 362); // 362.20 (inverse only; maraging itself is out of scope)
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
    const e = estimateSteelHvFromYield(900, { materialClass: cls, composition: LOW_ALLOY_4140 });
    assert.equal(e.hv, null, cls);
    assert.equal(e.status, "unavailable");
    assert.match(e.note, /^Unavailable: no verified hardness-strength relation for this alloy class/);
  }
  assert.equal(estimateSteelHvFromYield(900, withC(0.75)).hv, 344);
  assert.equal(estimateSteelHvFromYield(900, withC(0.76)).hv, null);
  assert.match(estimateSteelHvFromYield(900, withC(undefined)).note, /carbon content unknown/);
  assert.match(estimateSteelHvFromYield(900, { materialClass: "non-austenitic-steel", composition: undefined }).note, /carbon content unknown/);
});

// Review B1: the class gate alone let stainless, duplex, PH, tool and maraging steels through with the P&V-T label
// (304 -> 474, 2205 -> 542, 17-4PH 444, H13 481, maraging 300 362 HV in the builder). Nominal compositions (wt%) below
// are typical grade values used as fixtures, not sourced data; what matters is which scope limit each one reaches.
const OUT_OF_SCOPE: Record<string, { comp: Record<string, number>; limit: RegExp }> = {
  "AISI 304": { comp: { Fe: 70.9, Cr: 18, Ni: 8, Mn: 2, Si: 0.75, C: 0.08 }, limit: /Cr 18 wt% >= 10\.5, stainless steel/ },
  "2205 duplex": { comp: { Fe: 67.6, Cr: 22, Ni: 5.5, Mo: 3.1, Mn: 1.5, N: 0.17, C: 0.03 }, limit: /Cr 22 wt% >= 10\.5/ },
  "17-4PH": { comp: { Fe: 74.5, Cr: 15.5, Ni: 4.5, Cu: 3.5, Nb: 0.3, Mn: 0.5, Si: 0.5, C: 0.05 }, limit: /Cr 15\.5 wt% >= 10\.5/ },
  "AISI H13": { comp: { Fe: 90.9, Cr: 5.2, Mo: 1.3, V: 1.0, Si: 1.0, Mn: 0.4, C: 0.4 }, limit: /Cr 5\.2 wt% >= 3, high-chromium tool/ },
  "Maraging 300": { comp: { Fe: 67.5, Ni: 18.5, Co: 9, Mo: 4.8, Ti: 0.6, Al: 0.1, C: 0.01 }, limit: /Ni 18\.5 wt% >= 5/ },
  "T1 high-speed (W)": { comp: { Fe: 75.2, W: 18, Cr: 4, V: 1, C: 0.75 }, limit: /Cr 4 wt% >= 3/ },
  "Co-only maraging-type": { comp: { Fe: 95, Co: 4, Mo: 0.5, C: 0.02 }, limit: /Co 4 wt% >= 1/ },
  "Hadfield-type Mn": { comp: { Fe: 86.8, Mn: 12.5, C: 0.7 }, limit: /Mn 12\.5 wt% >= 3/ },
};
// Inside P's data set: HSLA-100 (~3.5 Ni, ~1.6 Cu) and plain carbon / low-alloy grades.
const IN_SCOPE: Record<string, Record<string, number>> = {
  "HSLA-100": { Fe: 92.7, C: 0.04, Mn: 0.85, Ni: 3.5, Cu: 1.6, Cr: 0.6, Mo: 0.6, Nb: 0.03, Si: 0.25 },
  "AISI 1045": { Fe: 98.5, C: 0.45, Mn: 0.75, Si: 0.25 },
  "AISI 4140": LOW_ALLOY_4140,
  "AISI 4340": { Fe: 95.7, C: 0.4, Mn: 0.7, Ni: 1.8, Cr: 0.8, Mo: 0.25, Si: 0.25 },
};

test("B1 scope gate: stainless, duplex, PH, tool, high-speed, maraging and high-Mn steels are Unavailable", () => {
  for (const [name, { comp, limit }] of Object.entries(OUT_OF_SCOPE)) {
    const e = estimateSteelHvFromYield(900, { materialClass: "non-austenitic-steel", composition: comp });
    assert.equal(e.hv, null, name);
    assert.match(e.note, /^Unavailable: outside the regression's data set \(carbon and low-alloy steels only\)/, name);
    assert.match(e.note, limit, name);
    assert.doesNotMatch(e.note, /Pavlina/, name);
  }
  // first matching limit wins: Cr >= 10.5 is reported as stainless, not as the Cr >= 3 tool-steel limit
  assert.match(lowAlloyScopeViolation({ Cr: 12 })!, /stainless/);
  assert.equal(lowAlloyScopeViolation({ Cr: 2.99, Ni: 4.99, Co: 0.99, Mo: 1.49, W: 0.99, V: 0.49, Mn: 2.99 }), null);
});

test("B1 scope gate keeps carbon and low-alloy steels, HSLA-100 included (no naive total-alloy cap)", () => {
  for (const [name, comp] of Object.entries(IN_SCOPE)) {
    const e = estimateSteelHvFromYield(900, { materialClass: "non-austenitic-steel", composition: comp });
    assert.equal(e.hv, 344, name); // (900 + 90.7) / 2.876 = 344.47
    assert.equal(e.status, "estimate-pavlina-van-tyne-2008", name);
  }
});

test("B1 through both stores: stainless/duplex/PH/tool/maraging specimens get no HV", () => {
  for (const [name, { comp }] of Object.entries(OUT_OF_SCOPE)) {
    assert.equal(deriveProperties(comp, name, "Fe").hardness_HV, null, `builder ${name}`);
    const s = deriveSpecimenProperties(comp, name, "Fe");
    const e = estimateSpecimenHardnessHV({ baseMetal: s.baseMetal, crystalSystem: s.xrd.crystalSystem, composition: s.composition, unit: s.unit, yieldStrength_MPa: s.yieldStrength_25C_MPa });
    assert.equal(e.hv, null, `specimen store ${name}`);
  }
  // 304 nominal (Ni exactly 8): both stores now class it FCC (builder niEq parentheses fix; specimen store Ni >= 8)
  const ss304 = OUT_OF_SCOPE["AISI 304"].comp;
  assert.equal(deriveProperties(ss304, "304", "Fe").xrd.crystalSystem, "FCC");
  assert.equal(deriveSpecimenProperties(ss304, "304", "Fe").xrd.crystalSystem, "FCC");
  // HSLA-100 stays estimated in the builder
  const hsla = deriveProperties(IN_SCOPE["HSLA-100"], "HSLA-100", "Fe");
  assert.equal(hsla.xrd.crystalSystem, "BCC");
  assert.equal(hsla.hardnessHVStatus, "estimate-pavlina-van-tyne-2008");
  assert.equal(hsla.hardness_HV, Math.round((hsla.yieldStrength_25C_MPa + 90.7) / 2.876));
});

test("estimate note names the source, the validity range and 'not measured'", () => {
  const e = estimateSteelHvFromYield(1000, steel);
  assert.match(e.note, /^≈ 379 HV: estimate from yield strength by inverting the Pavlina & Van Tyne \(2008\) steel regression/);
  assert.match(e.note, /carbon and low-alloy steels, HV 129-632/);
  assert.match(e.note, /about ±35 HV/); // 102 / 2.876 = 35.5
  assert.match(e.note, /not measured$/);
  assert.match(SPECIMEN_HARDNESS_NOT_LOADED_NOTE, /no measured hardness/);
});

test("Tabor in consistent units: YS/3.1 is Tabor-like (c ~ 3.16), but it is not the steel regression", () => {
  const taborFactorMPaPerHV = 9.807 / 3; // flow stress (MPa) per HV (kgf/mm2), H = 3 sigma in consistent units
  assert.ok(Math.abs(taborFactorMPaPerHV - 3.269) < 0.001);
  assert.ok(Math.abs(9.807 / 3.1 - 3.164) < 0.001); // the old rule's implied constraint factor (not a units error)
  // the old rule HV = YS / 3.1 versus the regression at YS 1000 MPa: 323 vs 379 HV
  assert.notEqual(Math.round(1000 / 3.1), estimateSteelHvFromYield(1000, steel).hv);
});

test("material builder presets: no preset gets an estimate (none is a carbon/low-alloy steel)", () => {
  const derived = Object.fromEntries(
    Object.entries(MATERIAL_PRESETS).map(([k, p]) => [k, deriveProperties(p.composition, p.name, p.base, { category: p.category })])
  );
  // old: in718 406 (YS/3.05), custom-ni 494, hastelloy-x 336, ti64 346 (YS/2.9), ss316l 210, alsi10mg 115, cocr-bio 380
  for (const k of ["in718", "custom-ni-superalloy", "hastelloy-x", "ti64-gr5", "ss316l", "alsi10mg", "cocr-bio"]) {
    assert.equal(derived[k].hardness_HV, null, k);
    assert.equal(derived[k].hardnessHVStatus, "unavailable", k);
    assert.match(derived[k].hardnessHVNote!, /^Unavailable: no verified hardness-strength relation/, k);
  }
  // maraging 300: round 1 gave 362 (old 307); now outside the data set (Ni 18.5, Co 9)
  const m = derived["maraging300"];
  assert.equal(m.yieldStrength_25C_MPa, 951);
  assert.equal(m.hardness_HV, null);
  assert.match(m.hardnessHVNote!, /^Unavailable: outside the regression's data set .*Ni 18\.5 wt% >= 5/);
});

test("AlSi10Mg preset: finite liquidus and freezing range (absent Cu counts as 0; was NaN)", () => {
  const p = MATERIAL_PRESETS["alsi10mg"];
  const d = deriveProperties(p.composition, p.name, p.base);
  assert.ok(Number.isFinite(d.liquidus_C), String(d.liquidus_C));
  assert.ok(Number.isFinite(d.freezingRange_C), String(d.freezingRange_C));
  assert.equal(d.liquidus_C, Math.round(660 - (9.8 * 6.5 + 0.45 * 4.5 + 0 * 3))); // 594
  assert.equal(d.freezingRange_C, 594 - 570);
});

test("builder niEq parentheses: C, N and Mn count when Ni is present", () => {
  // niEq = Ni + 30 C + 30 N + 0.5 Mn; solvus = 727 + 8 Cr - 12 niEq (the store's own heuristic)
  const d = deriveProperties({ Fe: 80, Ni: 4, Mn: 2, C: 0.1, Cr: 1 }, "niEq fixture", "Fe");
  const niEq = 4 + 0.1 * 30 + 2 * 0.5; // 8 (was 4: only Ni counted)
  assert.equal(d.solvus_C, Math.round(727 + 1 * 8 - niEq * 12));
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
  type Migrated = { activeMaterialSpecimen: MaterialSpecimen; activeSpecimen: MaterialSpecimen; savedSpecimens: unknown[] };
  // An entry without yieldStrength_25C_MPa no longer keeps its stale HV (review NIT 2).
  const noYield = { name: "partial", hardness_HV: 210, metadata: { baseMetal: "Fe" }, xrd: { crystalSystem: "FCC" } };
  const migrated = migrateMaterialStoreState({ activeMaterialSpecimen: stale, activeSpecimen: stale, savedSpecimens: [stale, noYield, null, 5] }, 0) as Migrated;
  assert.equal(migrated.activeMaterialSpecimen.hardness_HV, null);
  assert.equal(migrated.activeSpecimen.hardness_HV, null);
  assert.equal((migrated.savedSpecimens[0] as MaterialSpecimen).hardness_HV, null);
  assert.equal((migrated.savedSpecimens[1] as MaterialSpecimen).hardness_HV, null); // was kept at 210
  assert.equal(migrated.savedSpecimens[2], null); // non-objects pass through the migration
  assert.equal(migrated.savedSpecimens[3], 5);
  const untouched = migrateMaterialStoreState({ activeMaterialSpecimen: stale }, 1) as Migrated;
  assert.equal(untouched.activeMaterialSpecimen.hardness_HV, 346);
  const atPct = withHardnessEstimate({ ...fresh, unit: "at_pct" });
  assert.equal(atPct.hardness_HV, null);
  assert.equal(atPct.hardnessHVNote, AT_PCT_HARDNESS_UNAVAILABLE_NOTE);
  // the specimen-store path gives the same at% wording (it gave "carbon content unknown" for an Fe record)
  const e = estimateSpecimenHardnessHV({ baseMetal: "Fe", crystalSystem: "BCC", composition: { Fe: 98, C: 1.8 }, unit: "at_pct", yieldStrength_MPa: 1000 });
  assert.equal(e.hv, null);
  assert.equal(e.note, AT_PCT_HARDNESS_UNAVAILABLE_NOTE);
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
    assert.match(p.hardness, /^≈ 209 HV: estimate from yield strength by inverting the Pavlina & Van Tyne \(2008\)/);

    useMaterialStore.getState().updateComposition({ Ti: 90, Al: 6, V: 4 }, "Ti fixture");
    p = payloads.at(-1)!;
    assert.equal(p.hardnessHV, null);
    assert.equal(p.hardnessHVSource, "unavailable");
    assert.match(p.hardness, /Titanium alloy/);

    // builder payload of an in-scope low-alloy steel: estimate with source "estimate-from-yield"
    useMaterialStore.getState().updateComposition(IN_SCOPE["AISI 4140"], "4140 fixture");
    p = payloads.at(-1)!;
    const b = useMaterialStore.getState().activeMaterialSpecimen;
    assert.equal(p.hardnessHV, Math.round((b.yieldStrength_25C_MPa + 90.7) / 2.876));
    assert.equal(p.hardnessHVSource, "estimate-from-yield");
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
