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

// Todo until measured benchmark curves are added to TAFEL_BENCHMARK_DATASETS (it is empty since the PRNG-fabricated
// curves were removed with the BUG 1 fix). The test asserts a non-empty list, so it cannot pass vacuously meanwhile.
test('autoFitTafel fits every benchmark dataset without NaN or infinite outputs', { todo: 'waits for measured benchmark curves (TAFEL_BENCHMARK_DATASETS is empty)' }, () => {
  const datasets = mod().TAFEL_BENCHMARK_DATASETS;
  assert.ok(datasets.length > 0);
  for (const dataset of datasets) {
    const fit = mod().autoFitTafel(dataset);
    for (const key of ['eCorr', 'iCorr_uA_cm2', 'betaA_V_dec', 'betaC_V_dec', 'corrosionRateMmYr', 'rp_ohm_cm2', 'anodicR2', 'cathodicR2'] as const) {
      assert.ok(Number.isFinite(fit[key]), `${dataset.id} ${key} = ${fit[key]}`);
    }
  }
});
