import React from "react";
import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import type { TafelDataset, TafelFitResult, TafelRawPoint } from "../src/types/tafel";
import {
  TAFEL_BENCHMARK_DATASETS,
  TafelFitUnavailableError,
  autoFitTafel,
  exportTafelToCSV,
  isTafelFitComplete,
  tryAutoFitTafel,
} from "../src/utils/tafelParser";
import { executePythonTafelFit } from "../src/utils/tafelPythonService";
import {
  UNAVAILABLE_TEXT,
  fmtTafelNumber,
  fmtTafelQuantity,
  fmtTafelR2,
  tafelUnavailableReason,
} from "../src/utils/tafelDisplay";
import { fallbackClientTafelCorrosionRate } from "../src/services/pythonComputationService";
import { TafelPolarizationLab } from "../src/components/TafelPolarizationLab";
import { DigitalTwinProvider } from "../src/context/DigitalTwinContext";
import { D3TafelPolarizationChart } from "../src/components/D3TafelPolarizationChart";
import { PythonAnnualCorrosionRateModule } from "../src/components/PythonAnnualCorrosionRateModule";

// Engine-fix lane (audit defect 6a): a missing Tafel branch is "Unavailable" with a reason. The old engines answered a
// cathodic-only scan with an invented beta_a = 100 mV/dec and "R2 = 0.85" (client: m = +10 / -8.33), and a missing
// corrosion current with 1.25 uA/cm2. Oracle: analytic Butler-Volmer curve i = icorr * |10^(eta/ba) - 10^(-eta/bc)|.

const ECORR = -0.3;
const ICORR = 2.0;
const BETA_A = 0.06;
const BETA_C = 0.12;

function bvDataset(offsets: number[], overrides: Partial<TafelDataset["metadata"]> = {}): TafelDataset {
  const points: TafelRawPoint[] = offsets.map((eta, index) => {
    const signed = ICORR * (Math.pow(10, eta / BETA_A) - Math.pow(10, -eta / BETA_C));
    const density = Math.max(1e-10, Math.abs(signed));
    return {
      index,
      potential: ECORR + eta,
      currentRaw: signed * 1e-6,
      currentUnit: "A",
      currentDensity_uA_cm2: density,
      logCurrentDensity: Math.log10(density),
      signedCurrentDensity_uA_cm2: signed,
    };
  });
  return {
    id: "synthetic-bv",
    name: "synthetic bv",
    sourceFilename: "synthetic.csv",
    sourceInstrument: "csv",
    points,
    metadata: {
      electrodeAreaCm2: 1,
      referenceElectrode: "SCE",
      refOffsetVsSHE: 0.241,
      alloyName: "test alloy",
      density_g_cm3: 8,
      equivalentWeight: 25.68,
      electrolyte: "synthetic",
      temperatureC: 25,
      ...overrides,
    },
  };
}

// 10 mV grid shifted so that no point sits at Ecorr (i = 0 there)
const FULL = Array.from({ length: 61 }, (_, k) => -0.3 + 0.01 * k + 0.0025);
const CATHODIC_ONLY = FULL.filter((eta) => eta < 0);
const ANODIC_ONLY = FULL.filter((eta) => eta > 0);

const within = (actual: number, expected: number, fraction: number) =>
  Math.abs(actual - expected) <= fraction * Math.abs(expected);

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("a complete Butler-Volmer scan still fits both branches (no unavailable block)", () => {
  const fit = tryAutoFitTafel(bvDataset(FULL));
  assert.equal(fit.fitStatus, undefined);
  assert.equal(fit.unavailable, undefined);
  assert.ok(isTafelFitComplete(fit));
  assert.ok(within(fit.iCorr_uA_cm2!, ICORR, 0.15), `icorr ${fit.iCorr_uA_cm2}`);
  assert.ok(within(fit.betaA_V_dec!, BETA_A, 0.1), `betaA ${fit.betaA_V_dec}`);
  assert.ok(within(fit.betaC_V_dec!, BETA_C, 0.1), `betaC ${fit.betaC_V_dec}`);
  assert.ok(fit.anodicR2! > 0.99 && fit.cathodicR2! > 0.99);
  assert.ok(fit.syntheticButlerVolmer.length > 0);
  // autoFitTafel returns the same complete fit
  assert.equal(autoFitTafel(bvDataset(FULL)).iCorr_uA_cm2, fit.iCorr_uA_cm2);
});

test("cathodic-only scan: no invented anodic slope or R2, no intersection, no rate", () => {
  const fit = tryAutoFitTafel(bvDataset(CATHODIC_ONLY));
  assert.equal(fit.fitStatus, "unavailable");
  assert.match(fit.unavailable!.anodicBranch!, /Anodic branch unavailable: \d+ data point\(s\) in the fit window/);
  assert.equal(fit.unavailable!.cathodicBranch, undefined);
  for (const key of ["betaA_V_dec", "betaA_mV_dec", "anodicR2", "anodicSlope_m", "anodicIntercept_b"] as const) {
    assert.equal(fit[key], null, key);
  }
  for (const key of [
    "eCorr", "eCorrSHE", "iCorr_uA_cm2", "logIcorr", "totalCurrentIcorr_uA", "sternGearyB_V", "rp_ohm_cm2",
    "corrosionRateMmYr", "corrosionRateMpy", "massLoss_g_m2_day", "severity", "astmClassification",
  ] as const) {
    assert.equal(fit[key], null, key);
  }
  assert.notEqual(fit.anodicR2, 0.85);
  assert.notEqual(fit.betaA_mV_dec, 100);
  assert.deepEqual(fit.syntheticButlerVolmer, []);
  // the fitted cathodic branch is a real fit
  assert.ok(within(fit.betaC_V_dec!, BETA_C, 0.15), `betaC ${fit.betaC_V_dec}`);
  assert.ok(fit.cathodicR2! > 0.99 && fit.cathodicR2 !== 0.85);
  assert.ok(fit.tangentLines.some((t) => typeof t.logI_cathodic === "number"));
  assert.ok(fit.tangentLines.every((t) => t.logI_anodic === null));
  assert.equal(isTafelFitComplete(fit), false);
  assert.match(tafelUnavailableReason(fit), /Anodic branch unavailable/);
  assert.doesNotMatch(JSON.stringify(fit), /NaN|Infinity/);
});

test("anodic-only scan: no invented cathodic slope or R2", () => {
  const fit = tryAutoFitTafel(bvDataset(ANODIC_ONLY));
  assert.equal(fit.fitStatus, "unavailable");
  assert.match(fit.unavailable!.cathodicBranch!, /Cathodic branch unavailable/);
  assert.equal(fit.betaC_mV_dec, null);
  assert.equal(fit.cathodicR2, null);
  assert.notEqual(fit.cathodicR2, 0.85);
  assert.ok(within(fit.betaA_V_dec!, BETA_A, 0.15), `betaA ${fit.betaA_V_dec}`);
  assert.equal(fit.iCorr_uA_cm2, null);
});

test("autoFitTafel throws TafelFitUnavailableError carrying the partial fit instead of inventing numbers", () => {
  assert.throws(
    () => autoFitTafel(bvDataset(CATHODIC_ONLY)),
    (err: unknown) => {
      assert.ok(err instanceof TafelFitUnavailableError);
      assert.equal(err.fit.fitStatus, "unavailable");
      assert.equal(err.fit.betaA_mV_dec, null);
      assert.match(err.message, /Anodic branch unavailable/);
      return true;
    }
  );
});

test("a known manual i_corr gives the Faraday rate but never Rp or a slope for the missing branch", () => {
  const fit = tryAutoFitTafel(bvDataset(CATHODIC_ONLY), undefined, undefined, -0.3, 3.0);
  assert.equal(fit.fitStatus, "unavailable"); // the anodic branch is still unavailable
  assert.equal(fit.unavailable!.iCorr_uA_cm2, undefined);
  assert.ok(Math.abs(fit.iCorr_uA_cm2! - 3.0) < 1e-3);
  // CR = K1 * i * EW / rho with the exact F: 0.0032707148 * 3 * 25.68 / 8
  assert.ok(within(fit.corrosionRateMmYr!, (0.0032707148 * 3.0 * 25.68) / 8, 1e-3), `CR ${fit.corrosionRateMmYr}`);
  assert.equal(fit.rp_ohm_cm2, null);
  assert.equal(fit.sternGearyB_V, null);
  assert.equal(fit.betaA_mV_dec, null);
  assert.notEqual(fit.severity, null);
});

test("a dataset without equivalent weight / density has no Faraday rate (no 316L substitution)", () => {
  const fit = tryAutoFitTafel(bvDataset(FULL, { equivalentWeight: 0, density_g_cm3: 0 }));
  assert.equal(fit.fitStatus, "unavailable");
  assert.match(fit.unavailable!.substrate!, /no equivalent weight/);
  assert.equal(fit.corrosionRateMmYr, null);
  assert.equal(fit.severity, null);
  assert.ok(fit.iCorr_uA_cm2 !== null); // the fitted i_corr itself is still reported
});

test("CSV export prints Unavailable for missing values and the reason", () => {
  const dataset = bvDataset(CATHODIC_ONLY);
  const csv = exportTafelToCSV(dataset, tryAutoFitTafel(dataset));
  assert.match(csv, /# Anodic Tafel Slope \(Beta_a\): Unavailable \(R2: Unavailable\)/);
  assert.match(csv, /# Corrosion Current Density \(i_corr\): Unavailable/);
  assert.match(csv, /# Faraday Penetration Rate: Unavailable \(Unavailable\)/);
  assert.match(csv, /# Unavailable: Anodic branch unavailable/);
  assert.doesNotMatch(csv, /null|NaN/);
});

test("tafelDisplay formats null and non-finite values as Unavailable", () => {
  assert.equal(fmtTafelNumber(null), UNAVAILABLE_TEXT);
  assert.equal(fmtTafelNumber(undefined), UNAVAILABLE_TEXT);
  assert.equal(fmtTafelNumber(Number.NaN), UNAVAILABLE_TEXT);
  assert.equal(fmtTafelNumber(1.25, { digits: 3 }), "1.250");
  assert.equal(fmtTafelQuantity(null, "mV/dec"), UNAVAILABLE_TEXT);
  assert.equal(fmtTafelQuantity(120, "mV/dec"), "120 mV/dec");
  assert.equal(fmtTafelQuantity(18951, "Ω·cm²", { grouped: true }), "18,951 Ω·cm²");
  assert.equal(fmtTafelR2(null), "R²: Unavailable");
  assert.equal(fmtTafelR2(0.9981), "R² = 0.9981");
});

// ---- Python response mapping ------------------------------------------------------------------------------------

function stubJson(body: unknown) {
  globalThis.fetch = (async () =>
    new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } })) as any;
}

test("executePythonTafelFit keeps the engine's null values as null (Number(null) would be 0)", async () => {
  stubJson({
    success: true,
    fitStatus: "unavailable",
    unavailableReason: "Anodic branch unavailable: 0 data point(s) in the fit window [-0.20, -0.10] V (at least 3 are required)",
    unavailable: { anodicBranch: "Anodic branch unavailable: 0 data point(s)" },
    eCorr: null, iCorr_uA_cm2: null, logIcorr: null,
    betaA_mV_dec: null, betaA_V_dec: null, betaC_mV_dec: 119.2, betaC_V_dec: 0.1192,
    anodicSlope_dLogI_dE: null, cathodicSlope_dLogI_dE: -8.39, anodicR2: null, cathodicR2: 0.9993,
    sternGearyB_V: null, rp_ohm_cm2: null, corrosionRateMmYr: null, corrosionRateMpy: null, massLoss_g_m2_day: null,
    severity: null, rawEcorrValley: -0.3, rawIcorrValley: 0.5,
    cathodicRange: [-0.52, -0.34], anodicRange: [-0.26, -0.1],
    tangentLines: [], fittedButlerVolmer: [], pythonVersion: "3.12.10", durationMs: 1.2,
  });
  const fit = await executePythonTafelFit(bvDataset(CATHODIC_ONLY));
  assert.equal(fit.isPythonEngine, true);
  assert.equal(fit.fitStatus, "unavailable");
  assert.match(fit.unavailableReason!, /Anodic branch unavailable/);
  for (const key of [
    "eCorr", "eCorrSHE", "iCorr_uA_cm2", "logIcorr", "totalCurrentIcorr_uA", "betaA_V_dec", "betaA_mV_dec",
    "anodicR2", "anodicSlope_m", "sternGearyB_V", "rp_ohm_cm2", "corrosionRateMmYr", "corrosionRateMpy",
    "massLoss_g_m2_day", "severity", "astmClassification", "anodicIntercept_b", "cathodicIntercept_b",
  ] as const) {
    assert.equal(fit[key], null, key);
  }
  assert.equal(fit.betaC_mV_dec, 119.2);
  assert.equal(fit.cathodicR2, 0.9993);
  assert.equal(fit.cathodicSlope_m, -8.39);
  assert.equal(fit.rawEcorrValley, -0.3);
});

test("executePythonTafelFit no longer invents R2 0.95, slopes -8.33 / 10, intercept 0 or fit windows", async () => {
  stubJson({
    success: true, eCorr: -0.3, iCorr_uA_cm2: 2, logIcorr: 0.301, betaA_V_dec: 0.06, betaA_mV_dec: 60,
    betaC_V_dec: 0.12, betaC_mV_dec: 120, sternGearyB_V: 0.0173, rp_ohm_cm2: 8650, corrosionRateMmYr: 0.0214,
    corrosionRateMpy: 0.84, massLoss_g_m2_day: 0.45, rawEcorrValley: -0.3, rawIcorrValley: 0.1,
    cathodicRange: [-0.5, -0.34], anodicRange: [-0.26, -0.1], tangentLines: [],
    // no R2 / slope keys
  });
  const fit = await executePythonTafelFit(bvDataset(FULL));
  assert.equal(fit.anodicR2, null);
  assert.equal(fit.cathodicR2, null);
  assert.equal(fit.anodicSlope_m, null);
  assert.equal(fit.cathodicSlope_m, null);
  assert.equal(fit.cathodicIntercept_b, null);
  assert.equal(fit.iCorr_uA_cm2, 2);
  assert.equal(fit.severity, "Passivated / Good"); // 0.0214 mm/yr
  // a response without its fit windows is malformed: the call falls back to the client fit instead of inventing ranges
  stubJson({ success: true, eCorr: -0.3, iCorr_uA_cm2: 2, rawEcorrValley: -0.3, rawIcorrValley: 0.1 });
  const local = await executePythonTafelFit(bvDataset(FULL));
  assert.equal(local.isPythonEngine, false);
});

// ---- client annual-rate fallback ---------------------------------------------------------------------------------

test("client annual-rate fallback: a missing i_corr is unavailable, not 1.25 uA/cm2", () => {
  const res = fallbackClientTafelCorrosionRate({ alloyId: "steel-316l", density_g_cm3: 7.98, equivalentWeight: 24.8205 });
  assert.equal(res.status, "unavailable");
  assert.match(res.unavailableReason!, /iCorr_uA_cm2 was not supplied/);
  for (const key of ["corrosionRateMmYr", "corrosionRateMpy", "sternGearyB_V", "rp_ohm_cm2", "iCorr_uA_cm2", "severity", "rulUniformYears"] as const) {
    assert.equal(res[key], null, key);
  }
  assert.deepEqual(res.timelineProjections, []);
  assert.doesNotMatch(JSON.stringify(res), /1\.25|NaN/);
});

test("client annual-rate fallback: no substrate, no invented 316L preset", () => {
  const res = fallbackClientTafelCorrosionRate({ alloyId: "duplex2205", iCorr_uA_cm2: 2 });
  assert.equal(res.status, "unavailable");
  assert.match(res.unavailable!.substrate, /cannot resolve an alloy preset/);
  assert.equal(res.corrosionRateMmYr, null);
});

test("client annual-rate fallback: missing slopes leave only Stern-Geary B and Rp unavailable", () => {
  const res = fallbackClientTafelCorrosionRate({ iCorr_uA_cm2: 2, density_g_cm3: 8, equivalentWeight: 25.68, alloyId: "x" });
  assert.equal(res.status, "partial");
  assert.equal(res.sternGearyB_V, null);
  assert.equal(res.rp_ohm_cm2, null);
  assert.ok(within(res.corrosionRateMmYr!, (0.0032707148 * 2 * 25.68) / 8, 1e-3));
  const full = fallbackClientTafelCorrosionRate({
    iCorr_uA_cm2: 2, betaA: 0.1, betaC: 0.12, density_g_cm3: 8, equivalentWeight: 25.68, alloyId: "x", activationEnergyJ_mol: 30000,
  });
  assert.equal(full.status, undefined);
  assert.ok(full.rp_ohm_cm2! > 0);
  assert.equal(full.temperatureSensitivity.length, 9);
});

// ---- UI markup ---------------------------------------------------------------------------------------------------

test("D3 chart summary and header show Unavailable for an unavailable fit (never null / NaN)", () => {
  const dataset = bvDataset(CATHODIC_ONLY);
  const html = renderToStaticMarkup(<D3TafelPolarizationChart dataset={dataset} fitResult={tryAutoFitTafel(dataset)} />);
  assert.match(html, /E_corr: Unavailable/);
  assert.match(html, /i_corr: Unavailable/);
  assert.match(html, /CR: <strong[^>]*>Unavailable<\/strong>/);
  assert.match(html, /β_a = Unavailable/);
  assert.doesNotMatch(html, /null|NaN|undefined|>0 Ω|100 mV|0\.85/);
});

test("annual-rate module banner shows the Tafel fit as Unavailable with its reason", () => {
  const dataset = bvDataset(CATHODIC_ONLY);
  const fit: TafelFitResult = tryAutoFitTafel(dataset);
  const html = renderToStaticMarkup(<PythonAnnualCorrosionRateModule tafelFit={fit} dataset={dataset} />);
  assert.match(html, /Tafel fit Unavailable: Anodic branch unavailable/);
  assert.doesNotMatch(html, /1\.25|null|NaN/);
  const none = renderToStaticMarkup(<PythonAnnualCorrosionRateModule tafelFit={null} dataset={dataset} />);
  assert.match(none, /no default value is used/);
  assert.doesNotMatch(none, /benchmark reference values|1\.25/);
});

test("the lab shows Unavailable results and the reason for a cathodic-only scan (no invented slope, R2 or rate)", () => {
  TAFEL_BENCHMARK_DATASETS.push(bvDataset(CATHODIC_ONLY));
  try {
    const html = renderToStaticMarkup(
      <DigitalTwinProvider>
        <TafelPolarizationLab />
      </DigitalTwinProvider>
    );
    assert.match(html, /Tafel result: Unavailable/);
    assert.match(html, /Anodic branch unavailable/);
    assert.match(html, /Anodic Slope β_a: <strong[^>]*>Unavailable<\/strong>/);
    assert.match(html, /R²: Unavailable/);
    assert.doesNotMatch(html, /Fit R² = 0\.85|100 mV\/dec|>NaN<|>null<| null | NaN /);
    // result cards
    assert.match(html, /Polarization Res\. \(Rp\)[\s\S]{0,300}Unavailable/);
    assert.match(html, /Corrosion Rate \(CR\)[\s\S]{0,300}Unavailable/);
  } finally {
    TAFEL_BENCHMARK_DATASETS.length = 0;
  }
});

// ---- review fix round: Digital Twin payload, drawing anchors, exact constants, reported substitution ----------------

import { readFileSync } from "node:fs";
import { MILS_PER_MM, digitalTwinElectrochemistry, tafelIntersectionAnchors } from "../src/utils/tafelDisplay";

test("Digital Twin sync sends null values and 'Unresolved' for an unavailable fit (never 'Active Dissolution')", () => {
  const dataset = bvDataset(CATHODIC_ONLY);
  const payload = digitalTwinElectrochemistry(tryAutoFitTafel(dataset));
  assert.equal(payload.passivationQuality, "Unresolved");
  assert.equal(payload.corrosionRateMpy, null);
  assert.equal(payload.openCircuitPotentialEcorrV, null);
  assert.equal(payload.polarizationResistanceRpOhmCm2, null);
  assert.equal(payload.eisImpedanceModuleOhm, null);
  const complete = digitalTwinElectrochemistry(tryAutoFitTafel(bvDataset(FULL)));
  assert.equal(typeof complete.corrosionRateMpy, "number");
  assert.equal(typeof complete.openCircuitPotentialEcorrV, "number");
  const fit = (severity: TafelFitResult["severity"]) =>
    digitalTwinElectrochemistry({ ...tryAutoFitTafel(bvDataset(FULL)), severity }).passivationQuality;
  assert.equal(fit("Immune / Highly Resistant"), "Immune");
  assert.equal(fit("Passivated / Good"), "Passive Stable");
  assert.equal(fit("Moderate (Caution)"), "Susceptible to Pitting");
  assert.equal(fit("Severe Rapid Corrosion"), "Active Dissolution");
  assert.equal(fit(null), "Unresolved");
});

test("chart anchors: an unavailable intersection is not drawn and the scales anchor on the measured valley", () => {
  const unavailable = tryAutoFitTafel(bvDataset(CATHODIC_ONLY));
  const a = tafelIntersectionAnchors(unavailable);
  assert.equal(a.intersectionKnown, false);
  assert.equal(a.eCorrRef, unavailable.rawEcorrValley);
  assert.ok(Math.abs(a.logIcorrRef - Math.log10(unavailable.rawIcorrValley)) < 1e-12);
  const complete = tryAutoFitTafel(bvDataset(FULL));
  const b = tafelIntersectionAnchors(complete);
  assert.equal(b.intersectionKnown, true);
  assert.equal(b.eCorrRef, complete.eCorr);
  assert.equal(b.logIcorrRef, complete.logIcorr);
  // a known manual E_corr without i_corr is still not an intersection
  assert.equal(tafelIntersectionAnchors({ ...unavailable, eCorr: -0.3, logIcorr: null }).intersectionKnown, false);
});

test("the D3 chart and the lab use the tested helpers (the drawing branches are not copies of them)", () => {
  const d3 = readFileSync(new URL("../src/components/D3TafelPolarizationChart.tsx", import.meta.url), "utf8");
  assert.match(d3, /const \{ intersectionKnown, eCorrRef, logIcorrRef \} = tafelIntersectionAnchors\(fitResult\)/);
  assert.match(d3, /if \(intersectionKnown\) \{/);
  assert.match(d3, /showDomainShading && intersectionKnown/);
  const lab = readFileSync(new URL("../src/components/TafelPolarizationLab.tsx", import.meta.url), "utf8");
  assert.match(lab, /electrochemistry: digitalTwinElectrochemistry\(fitResult\)/);
});

test("Stern-Geary B uses ln(10) and mpy the exact mil (not 2.302585 / 39.37 / 39.3701)", () => {
  assert.equal(MILS_PER_MM, 1000 / 25.4);
  // A large known i_corr gives a rate of several mm/yr, so the printed rounding is below 1e-6 relative.
  const fit = tryAutoFitTafel(bvDataset(FULL), undefined, undefined, -0.3, 600);
  assert.ok(Math.abs(fit.corrosionRateMpy! / fit.corrosionRateMmYr! / MILS_PER_MM - 1) < 2e-6);
  const full = tryAutoFitTafel(bvDataset(FULL));
  const ba = full.betaA_V_dec!;
  const bc = full.betaC_V_dec!;
  assert.ok(Math.abs(full.sternGearyB_V! - (ba * bc) / (Math.LN10 * (ba + bc))) < 6e-5); // B printed to 4 decimals
  const res = fallbackClientTafelCorrosionRate({
    iCorr_uA_cm2: 600, betaA: 0.1, betaC: 0.12, density_g_cm3: 8, equivalentWeight: 25.68, alloyId: "x",
  });
  assert.ok(Math.abs(res.corrosionRateMpy! / res.corrosionRateMmYr! / MILS_PER_MM - 1) < 2e-6);
  assert.equal(res.sternGearyB_V, +((0.1 * 0.12) / (Math.LN10 * 0.22)).toFixed(5));
});

test("a far Evans intersection is reported as a substitution by the measured valley, not substituted silently", () => {
  const offsets: Array<[number, number]> = [[-0.30, 0.1]];
  for (let k = 0; k < 10; k++) {
    const e = -0.52 + 0.02 * k;
    offsets.push([e, Math.pow(10, 9.0 - 8.0 * (e + 0.34))]);
  }
  for (let k = 0; k < 9; k++) {
    const e = -0.25 + 0.02 * k;
    offsets.push([e, Math.pow(10, 0.08 + 10.0 * (e + 0.26))]);
  }
  const dataset = bvDataset([]);
  dataset.points = offsets.map(([potential, density], index) => ({
    index, potential, currentRaw: density * 1e-6, currentUnit: "A" as const,
    currentDensity_uA_cm2: density, logCurrentDensity: Math.log10(density), signedCurrentDensity_uA_cm2: density,
  }));
  const fit = tryAutoFitTafel(dataset);
  assert.equal(fit.eCorr, -0.3); // the measured valley, as before
  assert.equal(fit.intersectionStatus, "substituted-measured-valley");
  assert.match(fit.intersectionNote!, /from the measured current valley \(limit 0\.15 V\)/);
  assert.equal(fit.fitStatus, undefined); // both branches were fitted
  // manual E_corr and i_corr both given: nothing was substituted any more
  const manual = tryAutoFitTafel(dataset, undefined, undefined, -0.31, 2.0);
  assert.equal(manual.intersectionStatus, undefined);
  // a normal scan has no note
  assert.equal(tryAutoFitTafel(bvDataset(FULL)).intersectionStatus, undefined);
});

test("executePythonTafelFit carries the engine's intersection note", async () => {
  stubJson({
    success: true, eCorr: -0.3, iCorr_uA_cm2: 2, logIcorr: 0.301, betaA_V_dec: 0.06, betaA_mV_dec: 60,
    betaC_V_dec: 0.12, betaC_mV_dec: 120, sternGearyB_V: 0.0173, rp_ohm_cm2: 8650, corrosionRateMmYr: 0.0214,
    corrosionRateMpy: 0.84, massLoss_g_m2_day: 0.45, rawEcorrValley: -0.3, rawIcorrValley: 0.1,
    cathodicRange: [-0.5, -0.34], anodicRange: [-0.26, -0.1], tangentLines: [],
    intersectionStatus: "substituted-measured-valley", intersectionNote: "the Evans intersection is far away",
  });
  const fit = await executePythonTafelFit(bvDataset(FULL));
  assert.equal(fit.intersectionStatus, "substituted-measured-valley");
  assert.equal(fit.intersectionNote, "the Evans intersection is far away");
});

test("the Tafel fit request no longer sends a default 316L alloyId", async () => {
  let body: any = null;
  globalThis.fetch = (async (_url: string, init: any) => {
    body = JSON.parse(init.body);
    return new Response("{}", { status: 500 });
  }) as any;
  await executePythonTafelFit(bvDataset(FULL));
  assert.equal(body.alloyId, undefined);
  assert.equal(body.equivalentWeight, 25.68);
});
