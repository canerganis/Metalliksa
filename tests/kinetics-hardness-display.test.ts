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
