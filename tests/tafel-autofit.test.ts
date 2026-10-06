import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { TafelDataset, TafelRawPoint } from '../src/types/tafel';

// BUG 1 (fixed in Phase 6a step b): src/utils/tafelParser.ts used to build TAFEL_BENCHMARK_DATASETS at module load
// through createBenchmarkDataset(), which always throws, so the module could not be imported and these tests were todo.
// The module is imported directly now: a regression fails this file loudly instead of turning tests into todos.
import * as tafel from '../src/utils/tafelParser';

const mod = () => tafel;

const ECORR = -0.3;
const ICORR = 2.0; // uA/cm2
const BETA_A = 0.1; // V/dec
const BETA_C = 0.12; // V/dec

/** Noise-free Butler-Volmer curve, i = icorr * |10^(eta/ba) - 10^(-eta/bc)|, on a 5 mV grid offset from Ecorr. */
function syntheticBv(): TafelDataset {
  const points: TafelRawPoint[] = [];
  for (let k = 0; k <= 220; k++) {
    const potential = -0.6 + k * 0.005 + 0.0013;
    const eta = potential - ECORR;
    const signed = ICORR * (Math.pow(10, eta / BETA_A) - Math.pow(10, -eta / BETA_C));
    const density = Math.max(1e-10, Math.abs(signed));
    points.push({
      index: k,
      potential,
      currentRaw: signed * 1e-6,
      currentUnit: 'A',
      currentDensity_uA_cm2: density,
      logCurrentDensity: Math.log10(density),
      signedCurrentDensity_uA_cm2: signed,
    });
  }
  return {
    id: 'synthetic-bv',
    name: 'synthetic bv',
    sourceFilename: 'synthetic.csv',
    sourceInstrument: 'csv',
    points,
    metadata: {
      electrodeAreaCm2: 1,
      referenceElectrode: 'SCE',
      refOffsetVsSHE: 0.241,
      alloyName: 'test',
      density_g_cm3: 8,
      equivalentWeight: 25.68,
      electrolyte: 'synthetic',
      temperatureC: 25,
    },
  };
}

const within = (actual: number, expected: number, fraction: number) =>
  Math.abs(actual - expected) <= fraction * Math.abs(expected);

test('autoFitTafel recovers Ecorr, icorr and both Tafel slopes of a synthetic Butler-Volmer curve (slopes 5 percent, icorr 10 percent)', () => {
  const fit = mod().autoFitTafel(syntheticBv());
  assert.ok(Math.abs(fit.eCorr - ECORR) < 0.01, `Ecorr ${fit.eCorr}`);
  // icorr carries a systematic ~6 percent low bias: the fit window starts 70 mV from Ecorr, where the opposing
  // branch of the Butler-Volmer curve still bends the semilog line. Slopes are within ~2 percent.
  assert.ok(within(fit.iCorr_uA_cm2, ICORR, 0.1), `icorr ${fit.iCorr_uA_cm2}`);
  assert.ok(within(fit.betaA_V_dec, BETA_A, 0.05), `betaA ${fit.betaA_V_dec}`);
  assert.ok(within(fit.betaC_V_dec, BETA_C, 0.05), `betaC ${fit.betaC_V_dec}`);
});

test('autoFitTafel Ecorr is reported vs SHE using the dataset reference offset', () => {
  const fit = mod().autoFitTafel(syntheticBv());
  assert.ok(Math.abs(fit.eCorrSHE - (fit.eCorr + 0.241)) < 1e-3);
});

test('autoFitTafel rejects datasets with too few points', () => {
  const data = syntheticBv();
  data.points = data.points.slice(0, 3);
  assert.throws(() => mod().autoFitTafel(data), /insufficient points/);
});

// Replaces the former todo "fits every benchmark dataset": no measured benchmark curves are bundled (the
// benchmark list was removed), so the fitter is exercised on a deterministic family of SYNTHETIC test fixtures
// generated in this file from the noise-free Butler-Volmer equation. They are not measurements and only check
// that the fitter recovers the parameters it was given and never emits NaN or infinite outputs.
const SYNTHETIC_BV_FAMILY = [
  { id: 'synthetic-bv-a', eCorr: -0.3, iCorr: 2.0, betaA: 0.1, betaC: 0.12 },
  { id: 'synthetic-bv-b', eCorr: -0.45, iCorr: 0.5, betaA: 0.06, betaC: 0.15 },
  { id: 'synthetic-bv-c', eCorr: -0.2, iCorr: 15.0, betaA: 0.12, betaC: 0.08 },
  { id: 'synthetic-bv-d', eCorr: -0.35, iCorr: 0.05, betaA: 0.09, betaC: 0.1 },
] as const;

function syntheticBvWith(p: (typeof SYNTHETIC_BV_FAMILY)[number]): TafelDataset {
  const dataset = syntheticBv();
  dataset.id = p.id;
  dataset.name = `${p.id} (synthetic Butler-Volmer test fixture)`;
  dataset.points = dataset.points.map((point, index) => {
    const potential = p.eCorr - 0.3 + index * 0.005 + 0.0013;
    const eta = potential - p.eCorr;
    const signed = p.iCorr * (Math.pow(10, eta / p.betaA) - Math.pow(10, -eta / p.betaC));
    const density = Math.max(1e-10, Math.abs(signed));
    return { ...point, potential, currentRaw: signed * 1e-6, currentDensity_uA_cm2: density,
      logCurrentDensity: Math.log10(density), signedCurrentDensity_uA_cm2: signed };
  });
  return dataset;
}

for (const p of SYNTHETIC_BV_FAMILY) {
  test(`autoFitTafel recovers the parameters of synthetic fixture ${p.id} with finite outputs`, () => {
    const fit = mod().autoFitTafel(syntheticBvWith(p));
    for (const key of ['eCorr', 'iCorr_uA_cm2', 'betaA_V_dec', 'betaC_V_dec', 'corrosionRateMmYr', 'rp_ohm_cm2', 'anodicR2', 'cathodicR2'] as const) {
      assert.ok(Number.isFinite(fit[key]), `${p.id} ${key} = ${fit[key]}`);
    }
    assert.ok(Math.abs(fit.eCorr - p.eCorr) < 0.01, `${p.id} Ecorr ${fit.eCorr}`);
    // Observed on this grid: icorr 2-6 percent low (same window bias as above), slopes within 2 percent.
    assert.ok(within(fit.iCorr_uA_cm2, p.iCorr, 0.1), `${p.id} icorr ${fit.iCorr_uA_cm2}`);
    assert.ok(within(fit.betaA_V_dec, p.betaA, 0.05), `${p.id} betaA ${fit.betaA_V_dec}`);
    assert.ok(within(fit.betaC_V_dec, p.betaC, 0.05), `${p.id} betaC ${fit.betaC_V_dec}`);
  });
}

test('autoFitTafel preserves an explicitly zero SHE reference offset', () => {
  const dataset = syntheticBv();
  dataset.metadata.referenceElectrode = 'SHE';
  dataset.metadata.refOffsetVsSHE = 0;
  const fit = mod().autoFitTafel(dataset);
  assert.notEqual(fit.eCorr, null);
  assert.equal(fit.eCorrSHE, fit.eCorr);
});
