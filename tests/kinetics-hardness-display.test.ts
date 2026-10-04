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
  formatCoolingRate,
  kineticsHardnessText,
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
  const lab = readFileSync(join(ROOT, "src", "components", "3d-distortion-lab", "IndustrialLPBFDecisionLab.tsx"), "utf8");
  assert.ok(!/predictedHardness_H(RC|V)\s*\?\?/.test(lab));
  // Hardness/primary phase come from the CCT row Python selected for the build cooling rate, never row 0.
  assert.match(lab, /kineticsHardnessText\(kineticsCct\.row\)/);
  assert.match(lab, /buildJobCctRow\(job\?\.kinetics\)/);
  assert.match(lab, /buildJobKineticsAvailability\(job\?\.kinetics\)/);
  assert.ok(!/cctContinuousCoolingMap\?\.\[0\]/.test(lab));
});

test("build-job kinetics: unavailable block (316L / AlSi10Mg) shows the reason, never a substituted alloy", () => {
  const unavailable = {
    success: false,
    status: "unavailable",
    reason: "no kinetics model for 316L Stainless Steel",
    alloyId: "ss316l",
    alloy: null,
    buildCoolingRate_C_s: 1205584,
    cctContinuousCoolingMap: null,
    calphadVsKineticsGap: null,
    buildCoolingRateCctRow: null,
  };
  assert.deepEqual(buildJobKineticsAvailability(unavailable), {
    available: false,
    reason: "no kinetics model for 316L Stainless Steel",
  });
  const sel = buildJobCctRow(unavailable);
  assert.equal(sel.row, null);
  assert.equal(kineticsHardnessText(sel.row).hrcValue, "Unavailable");
  assert.equal(buildJobKineticsAvailability(null).available, false);
  assert.equal(buildJobKineticsAvailability({ status: "available", calphadVsKineticsGap: null }).available, false);
});

test("build-job kinetics: the Python-selected CCT row is shown with its cooling rate; none outside the map", () => {
  const { rows } = goldenRows("in718_lpbf_quench.json");
  const gap = { kineticRealityAtSelectedCooling: { predictedMartensite_pct: 0, verdict: "x" } };
  const index = rows.findIndex((r) => r.coolingRate_C_s === 25);
  const inside = {
    status: "available",
    buildCoolingRate_C_s: 30,
    cctContinuousCoolingMap: rows,
    calphadVsKineticsGap: gap,
    buildCoolingRateCctRow: { status: "selected", rowIndex: index, rowCoolingRate_C_s: 25, buildCoolingRate_C_s: 30 },
  };
  assert.equal(buildJobKineticsAvailability(inside).available, true);
  const sel = buildJobCctRow(inside);
  assert.equal(sel.row, rows[index]);
  assert.notEqual(index, 0);
  assert.equal(sel.label, "CCT row 25 °C/s (nearest on a log scale to the build cooling rate 30 °C/s).");

  const above = {
    ...inside,
    buildCoolingRate_C_s: 1089047,
    buildCoolingRateCctRow: {
      status: "unavailable",
      rowIndex: null,
      reason: "build cooling rate 1.09e+06 C/s is above the CCT map range 0.05-2000 C/s; no row is extrapolated",
    },
  };
  const none = buildJobCctRow(above);
  assert.equal(none.row, null);
  assert.equal(
    none.label,
    "No CCT row: build cooling rate 1.09e+06 C/s is above the CCT map range 0.05-2000 C/s; no row is extrapolated."
  );
  assert.equal(kineticsHardnessText(none.row).hvValue, "Unavailable");
  // A selection that does not point at a real row is not trusted.
  assert.equal(buildJobCctRow({ ...inside, buildCoolingRateCctRow: { status: "selected", rowIndex: 99 } }).row, null);
  assert.equal(formatCoolingRate(2000), "2000");
  assert.equal(formatCoolingRate(1089047), "1.1e+6");
});
