import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { convertSteelHardness } from "../src/utils/hardnessConversion";
import {
  KINETICS_HV_STATUS_NOTES,
  buildJobCctRow,
  buildJobKineticsAvailability,
  buildJobMartensiteText,
  formatCoolingRate,
  kineticsCctRowText,
  kineticsHardnessText,
  kineticsLabelText,
  kineticsLswAvailability,
  kineticsModelBanner,
  kineticsPhaseSlices,
  kineticsStatusNote,
  kineticsValueText,
  kineticsVerdictSentence,
} from "../src/utils/kineticsHardnessDisplay";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), ".."); // cwd-independent
const STEP_B = join(ROOT, "python", "golden", "phase6a", "kinetics_ttt_cct_solver", "step_b");

type Row = {
  coolingRate_C_s: number;
  predictedHardness_HRC: number;
  predictedHardness_HV: number | null;
  predictedHardness_HV_status: string;
};
const goldenRows = (file: string): { type: string; rows: Row[] } => {
  const doc = JSON.parse(readFileSync(join(STEP_B, file), "utf8"));
  return { type: doc.stdout.alloyMetadata.type, rows: doc.stdout.cctContinuousCoolingMap };
};

test("kinetics hardness text: converted steel row", () => {
  const t = kineticsHardnessText({
    predictedHardness_HRC: 58,
    predictedHardness_HV: 653,
    predictedHardness_HV_status: "converted-astm-e140-table1",
  });
  assert.deepEqual(t, {
    hrcValue: "58",
    hvValue: "653",
    hrc: "58 HRC",
    hv: "653 HV",
    note: KINETICS_HV_STATUS_NOTES["converted-astm-e140-table1"],
  });
});

test("kinetics hardness text: null HV is Unavailable, never a number", () => {
  for (const status of [
    "unavailable-outside-e140-table1-hrc-20-68",
    "unavailable-no-verified-table-for-alloy-class",
  ]) {
    const t = kineticsHardnessText({ predictedHardness_HRC: 18, predictedHardness_HV: null, predictedHardness_HV_status: status });
    assert.equal(t.hv, "HV: Unavailable");
    assert.equal(t.hvValue, "Unavailable");
    assert.equal(t.hrc, "18 HRC");
    assert.equal(t.note, KINETICS_HV_STATUS_NOTES[status]);
  }
  // older payload without a status key
  assert.equal(kineticsHardnessText({ predictedHardness_HRC: 42, predictedHardness_HV: null }).note, "HV unavailable.");
});

test("kinetics hardness text: no solver row shows Unavailable instead of the old invented 52 HRC / 550 HV", () => {
  for (const row of [null, undefined, {}]) {
    const t = kineticsHardnessText(row);
    assert.equal(t.hrc, "HRC: Unavailable");
    assert.equal(t.hv, "HV: Unavailable");
    assert.equal(t.hrcValue, "Unavailable");
    assert.equal(t.hvValue, "Unavailable");
    assert.ok(!/52|550/.test(JSON.stringify(t)));
  }
  assert.equal(kineticsHardnessText({ predictedHardness_HRC: Number.NaN, predictedHardness_HV: Number.NaN }).hv, "HV: Unavailable");
});

test("re-blessed solver goldens: steel HV equals the shared TS E140 util; non-steel HV is null", () => {
  const files = readdirSync(STEP_B).filter((f) => f.endsWith(".json")).sort();
  assert.deepEqual(files, [
    "aisi4140_ui_defaults.json",
    "aisi4340_slow_cool.json",
    "in718_lpbf_quench.json",
    "ti64_beta_quench.json",
  ]);
  let converted = 0;
  for (const f of files) {
    const { type, rows } = goldenRows(f);
    assert.equal(rows.length, 10, f);
    for (const r of rows) {
      if (type.includes("Steel")) {
        // Python solver (hardness_conversion_e140) and TS util (convertSteelHardness) must agree.
        const ts = convertSteelHardness(r.predictedHardness_HRC, "HRC").HV;
        assert.equal(r.predictedHardness_HV, ts, `${f} ${r.coolingRate_C_s} C/s`);
        if (ts !== null) converted++;
        assert.equal(
          r.predictedHardness_HV_status,
          ts === null ? "unavailable-outside-e140-table1-hrc-20-68" : "converted-astm-e140-table1"
        );
      } else {
        assert.equal(r.predictedHardness_HV, null, `${f} ${r.coolingRate_C_s} C/s`);
        assert.equal(r.predictedHardness_HV_status, "unavailable-no-verified-table-for-alloy-class");
      }
    }
  }
  assert.equal(converted, 16);
});

test("Studio table text for the AISI 4140 UI-default golden (old -> new)", () => {
  const { rows } = goldenRows("aisi4140_ui_defaults.json");
  assert.deepEqual(
    rows.map((r) => {
      const t = kineticsHardnessText(r);
      return `${r.coolingRate_C_s}: ${t.hrc} (${t.hv})`;
    }),
    [
      "0.05: 18 HRC (HV: Unavailable)", // was 18 HRC (229 HV)
      "0.2: 18 HRC (HV: Unavailable)", // was 18 HRC (229 HV)
      "1: 28 HRC (286 HV)", // was 334
      "5: 28 HRC (286 HV)", // was 334
      "10: 42 HRC (412 HV)", // was 481
      "25: 42 HRC (412 HV)", // was 481
      "50: 54 HRC (577 HV)", // was 607
      "100: 58 HRC (653 HV)", // was 649
      "500: 58 HRC (653 HV)", // was 649
      "2000: 58 HRC (653 HV)", // was 649
    ]
  );
});

test("consumers: no invented hardness fallbacks, null HV goes through the display helper", () => {
  const studio = readFileSync(join(ROOT, "src", "components", "PhaseKineticsTTTCCTStudio.tsx"), "utf8");
  assert.ok(!/predictedHardness_HRC\s*\|\|/.test(studio));
  assert.ok(!/predictedHardness_HV\s*\|\|/.test(studio));
  assert.ok(!/\|\|\s*(52|550)\b/.test(studio));
  assert.ok(!/\{row\.predictedHardness_HV\}/.test(studio));
  assert.match(studio, /kineticsHardnessText\(row\)/);
  assert.match(studio, /kineticsHardnessText\(currentCCTMatch\)/);
  // The Decision Lab delegates the build-job kinetics block to the panel (render-tested in
  // tests/build-job-kinetics-panel.test.tsx); it reads no kinetics field itself.
  const lab = readFileSync(join(ROOT, "src", "components", "3d-distortion-lab", "IndustrialLPBFDecisionLab.tsx"), "utf8");
  assert.match(lab, /<BuildJobKineticsPanel kinetics=\{job\?\.kinetics\} \/>/);
  assert.ok(!/cctContinuousCoolingMap|calphadVsKineticsGap|predictedMartensite_pct|predictedHardness_H/.test(lab));
});

test("build-job kinetics: availability follows Python's status, not the legacy success flag", () => {
  assert.deepEqual(
    buildJobKineticsAvailability({ status: "unavailable", reason: "no kinetics model for 316L Stainless Steel" }),
    { available: false, reason: "no kinetics model for 316L Stainless Steel." }
  );
  assert.equal(buildJobKineticsAvailability(null).available, false);
  assert.equal(buildJobKineticsAvailability({}).available, false); // a pre-status payload is not trusted
  assert.equal(buildJobKineticsAvailability({ status: "available" }).available, true);
});

test("build-job kinetics: a CCT selection is trusted only when it matches its map row", () => {
  const rows = [{ coolingRate_C_s: 0.05 }, { coolingRate_C_s: 25, primaryMicrostructure: "Bainite" }];
  const base = { status: "available", cctContinuousCoolingMap: rows };
  const sel = { status: "selected", rowIndex: 1, rowCoolingRate_C_s: 25, buildCoolingRate_C_s: 30 };
  const ok = buildJobCctRow({ ...base, buildCoolingRateCctRow: sel });
  assert.equal(ok.row, rows[1]);
  assert.equal(ok.label, "CCT row 25 °C/s (nearest on a log scale to the build cooling rate 30 °C/s).");
  for (const bad of [
    { ...sel, rowIndex: 99 },
    { ...sel, rowIndex: 0 }, // index points at a row whose rate differs from rowCoolingRate_C_s
    { ...sel, rowCoolingRate_C_s: 50 },
    { ...sel, buildCoolingRate_C_s: null },
    { ...sel, status: "unavailable" },
  ]) {
    assert.equal(buildJobCctRow({ ...base, buildCoolingRateCctRow: bad }).row, null, JSON.stringify(bad));
  }
  assert.equal(
    buildJobCctRow({ ...base, buildCoolingRateCctRow: { status: "unavailable", reason: "r" } }).label,
    "No CCT row: r."
  );
});

test("build-job kinetics: martensite text never renders null% and never shows a withheld verdict", () => {
  assert.deepEqual(
    buildJobMartensiteText({ buildRateMartensite: { status: "available", predictedMartensite_pct: 7, verdict: "V", coolingRate_C_s: 30 } }),
    { value: "7%", verdict: "V", reason: "", hint: "At build rate 30 °C/s" }
  );
  for (const m of [
    { status: "available", predictedMartensite_pct: null, verdict: "V" },
    { status: "available", predictedMartensite_pct: Number.NaN, verdict: "V" },
    { status: "unavailable", predictedMartensite_pct: 7, verdict: "V", reason: "withheld" },
    null,
  ]) {
    const t = buildJobMartensiteText({ buildRateMartensite: m });
    assert.equal(t.value, "Unavailable");
    assert.equal(t.verdict, null);
    assert.ok(!/null|NaN|undefined/.test(`${t.value} ${t.reason} ${t.hint}`), JSON.stringify(t));
  }
});

test("formatCoolingRate: short, never a long float", () => {
  assert.equal(formatCoolingRate(2000), "2000");
  assert.equal(formatCoolingRate(0.05), "0.05");
  assert.equal(formatCoolingRate(1523.456789123), "1523");
  assert.equal(formatCoolingRate(30.123456), "30.12");
  assert.equal(formatCoolingRate(1089047), "1.09e+6");
});

// ---------------------------------------------------------------------------------------------------------------
// Engine-fix lane fx-kinetics: steel-only model, registry placeholders, TTT floor (python/kinetics_ttt_cct_solver.py).

const goldenDoc = (file: string) => JSON.parse(readFileSync(join(STEP_B, file), "utf8")).stdout;
const GOLDEN_FILES = ["aisi4140_ui_defaults.json", "aisi4340_slow_cool.json", "in718_lpbf_quench.json", "ti64_beta_quench.json"];
const BAD_TEXT = /null|NaN|undefined|Infinity/;

test("fx-kinetics: every visible CCT/hardness/phase text of the four goldens is clean (no null, NaN, undefined)", () => {
  for (const f of GOLDEN_FILES) {
    const doc = goldenDoc(f);
    for (const row of doc.cctContinuousCoolingMap) {
      const rt = kineticsCctRowText(row);
      const ht = kineticsHardnessText(row);
      const slices = kineticsPhaseSlices(row);
      const all = [...Object.values(rt), ...Object.values(ht), slices.reason, ...slices.slices.map((s) => `${s.name}${s.value}`)];
      for (const s of all) assert.ok(!BAD_TEXT.test(String(s)), `${f} ${row.coolingRate_C_s}: ${s}`);
    }
    const banner = kineticsModelBanner(doc.kineticsModel, doc.tttIncubationFloor);
    assert.ok(!BAD_TEXT.test(`${banner.reason}${banner.caution}${banner.floorLine ?? ""}`), f);
  }
});

test("fx-kinetics: non-steel goldens (IN718, Ti-6Al-4V) show Unavailable with the steel-only reason, never steel values", () => {
  for (const f of ["in718_lpbf_quench.json", "ti64_beta_quench.json"]) {
    const doc = goldenDoc(f);
    assert.equal(doc.tttIsothermalCurves, null);
    const banner = kineticsModelBanner(doc.kineticsModel, doc.tttIncubationFloor);
    assert.equal(banner.available, false);
    assert.equal(banner.reason, "kinetics model is steel-only.");
    assert.equal(banner.floorLine, null);
    for (const row of doc.cctContinuousCoolingMap) {
      const rt = kineticsCctRowText(row);
      assert.equal(rt.startTemp, "Unavailable", f);
      assert.equal(rt.startTime, "Unavailable");
      assert.equal(rt.microstructure, "Unavailable");
      assert.equal(rt.martensite, "Unavailable");
      assert.equal(rt.startNote, "Unavailable: kinetics model is steel-only.");
      const ht = kineticsHardnessText(row);
      assert.equal(ht.hrc, "HRC: Unavailable");
      assert.equal(ht.hv, "HV: Unavailable");
      assert.equal(ht.note, "Unavailable: kinetics model is steel-only.");
      const slices = kineticsPhaseSlices(row);
      assert.deepEqual(slices.slices, []);
      assert.equal(slices.reason, "Unavailable: kinetics model is steel-only.");
    }
    const gap = doc.calphadVsKineticsGap;
    assert.equal(kineticsLabelText(gap.equilibriumPrediction.stablePhasesAtRT), "Unavailable");
    assert.equal(kineticsValueText(gap.kineticRealityAtSelectedCooling.predictedMartensite_pct, "%"), "Unavailable");
    assert.equal(kineticsLabelText(gap.kineticRealityAtSelectedCooling.verdict), "Unavailable");
  }
});

test("fx-kinetics: registry placeholder Ms/Mf (IN718) are null in the golden and shown as Unavailable", () => {
  const doc = goldenDoc("in718_lpbf_quench.json");
  const crit = doc.criticalTransformationTemperatures;
  assert.equal(crit.Ms_C, null);
  assert.equal(crit.Mf_C, null);
  assert.equal(crit.Ms_C_status, "unavailable-registry-placeholder");
  assert.equal(kineticsValueText(crit.Ms_C, " °C"), "Unavailable");
  assert.equal(kineticsStatusNote(crit.Ms_C_status), "Unavailable: the registry value is a non-physical placeholder.");
  assert.equal(kineticsValueText(crit.CriticalCoolingRate_CCR_C_s, " °C/s"), "Unavailable");
  // Ti-6Al-4V Ms/Mf are not flagged in the registry: they stay numbers.
  assert.equal(kineticsValueText(goldenDoc("ti64_beta_quench.json").criticalTransformationTemperatures.Ms_C, " °C"), "800 °C");
});

test("fx-kinetics: steel goldens flag the TTT floor, CCT starts the floor drives are Unavailable", () => {
  const doc = goldenDoc("aisi4140_ui_defaults.json");
  const banner = kineticsModelBanner(doc.kineticsModel, doc.tttIncubationFloor);
  assert.equal(banner.available, true);
  assert.equal(banner.reason, "");
  assert.equal(
    banner.floorLine,
    "32 of 40 TTT points are on the 0.001 s incubation floor (floorHit): their start time is the floor, not a model value."
  );
  assert.equal(doc.tttIsothermalCurves.filter((p: { floorHit: boolean }) => p.floorHit).length, 32);
  for (const row of doc.cctContinuousCoolingMap) {
    // audit: "Pearlite starts at ~770 °C at every cooling rate" is no longer reported
    const rt = kineticsCctRowText(row);
    assert.equal(rt.startTemp, "Unavailable");
    assert.equal(rt.microstructure, "Unavailable");
    assert.match(rt.startNote, /no Ae3 asymptote; start not computed/);
    // the phase-fraction lookup is shown with its caveat
    assert.match(rt.fractionsNote, /lookup by cooling-rate band/);
  }
  const row100 = doc.cctContinuousCoolingMap.find((r: { coolingRate_C_s: number }) => r.coolingRate_C_s === 100);
  assert.equal(kineticsCctRowText(row100).martensite, "98%");
  assert.deepEqual(
    kineticsPhaseSlices(row100).slices.map((s) => `${s.name}:${s.value}`),
    ["Martensite:98", "Bainite:1", "Pearlite / Ferrite:0.5", "Retained Austenite:0.5"]
  );
  // an unknown status never produces a note from thin air
  assert.equal(kineticsStatusNote("something-else"), "");
  assert.equal(kineticsStatusNote(null), "");
  assert.equal(kineticsModelBanner(null, null).floorLine, null);
  assert.equal(kineticsModelBanner(null, null).available, false);
  assert.equal(kineticsCctRowText(null).startTemp, "Unavailable");
  assert.equal(kineticsCctRowText({ transformedStartTemp_C: Number.NaN }).startTemp, "Unavailable");
});

test("fx-kinetics: floor line only when at least one point is on the floor; LSW availability follows the solver", () => {
  const model = { status: "available", note: "n" };
  assert.equal(kineticsModelBanner(model, { pointCount: 40, floorHitCount: 0, floorValue_s: 0.001 }).floorLine, null);
  assert.equal(
    kineticsModelBanner(model, { pointCount: 40, floorHitCount: 1, floorValue_s: 0.001 }).floorLine,
    "1 of 40 TTT points are on the 0.001 s incubation floor (floorHit): their start time is the floor, not a model value."
  );
  assert.equal(kineticsModelBanner(model, { pointCount: null, floorHitCount: null }).floorLine, null);
  const unavailable = kineticsLswAvailability(
    [{ meanRadius_nm: null }, { meanRadius_nm: Number.NaN }],
    { status: "unavailable-aging-temperature-at-or-above-solvus", reason: "aging temperature 720 C is at or above the registry Ae3" }
  );
  assert.deepEqual(unavailable, { available: false, reason: "aging temperature 720 C is at or above the registry Ae3." });
  assert.equal(kineticsLswAvailability([{ meanRadius_nm: 2.5 }], null).available, true);
  assert.equal(
    kineticsLswAvailability(null, { status: "unavailable-aging-temperature-at-or-above-solvus" }).reason,
    "Unavailable: the aging temperature is at or above the registry solvus (steels: Ae1); no precipitate population."
  );
  // the verdict sentence follows the verdict and never claims shear for a diffusional verdict
  assert.match(kineticsVerdictSentence("Full Martensitic / Metastable Quench", 100, true), /athermally via shear/);
  assert.match(kineticsVerdictSentence("Mixed Microstructure (Martensite + Bainite)", 10, true), /part of the austenite/);
  assert.doesNotMatch(kineticsVerdictSentence("Diffusional Equilibrium Decomposition", 0.05, true), /shear/);
  assert.equal(kineticsVerdictSentence(null, 10, false), "Unavailable: kinetics model is steel-only.");
  assert.equal(kineticsVerdictSentence(null, 10, true), "");
  // registry-screening-value has a note (the Ti-6Al-4V Ms/Mf tooltips were empty)
  assert.notEqual(kineticsStatusNote("registry-screening-value"), "");
});

test("fx-kinetics: the Studio renders only through the null-safe helpers", () => {
  const studio = readFileSync(join(ROOT, "src", "components", "PhaseKineticsTTTCCTStudio.tsx"), "utf8");
  assert.ok(!/\{row\.transformedStartTemp_C\}/.test(studio));
  assert.ok(!/\{row\.transformedStartTime_s\}/.test(studio));
  assert.ok(!/\{row\.primaryMicrostructure\}/.test(studio));
  assert.ok(!/primaryMicrostructure\.includes/.test(studio));
  assert.ok(!/\{row\.phaseFractions\.Martensite_pct\}/.test(studio));
  assert.ok(!/\.Ms_C\} °C|\.Mf_C\} °C|critical_cooling_rate_C_s\} °C/.test(studio));
  assert.ok(!/predictedMartensite_pct\}%/.test(studio));
  assert.ok(!/Ferrite \+ Cementite|Complete Partitioning|Thermodynamically Forbidden/.test(studio));
  assert.match(studio, /typeof kineticsData\.criticalTransformationTemperatures\.Ms_C === "number"/);
  assert.match(studio, /kineticsCctRowText\(row\)/);
  assert.match(studio, /kineticsPhaseSlices\(currentCCTMatch\)/);
  assert.match(studio, /kineticsModelBanner\(kineticsData\?\.kineticsModel, kineticsData\?\.tttIncubationFloor\)/);
});
