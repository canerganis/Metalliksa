import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import type { TafelDataset, TafelRawPoint } from "../src/types/tafel";
import { TAFEL_INTERSECTION_MAX_OFFSET_V, tryAutoFitTafel } from "../src/utils/tafelParser";

// EUQ-13: the Python and TypeScript Tafel fits accepted the Evans intersection within different distances of the
// measured current valley (0.25 V vs 0.15 V), so an intersection 0.15-0.25 V away gave E_corr / i_corr differing by
// 10^(dE/beta_a) (about 46x for dE = 0.2 V, beta_a = 0.12 V/dec). The shared fixture is also run through the Python
// engine by python/test_tafel_physics_audit.py; both must reproduce its expected values.

interface FixtureCase {
  intersectionOffsetV: number;
  points: { potential: number; currentDensity_uA_cm2: number }[];
  expected: { eCorr: number; iCorr_uA_cm2: number; intersectionStatus: string | null };
}
const fixture = JSON.parse(readFileSync("tests/fixtures/tafel-intersection-offset.json", "utf8")) as {
  intersectionMaxOffsetV: number;
  cases: Record<string, FixtureCase>;
};

function dataset(c: FixtureCase): TafelDataset {
  const points: TafelRawPoint[] = c.points.map((p, index) => ({
    index,
    potential: p.potential,
    currentRaw: p.currentDensity_uA_cm2 * 1e-6,
    currentUnit: "A",
    currentDensity_uA_cm2: p.currentDensity_uA_cm2,
    logCurrentDensity: Math.log10(p.currentDensity_uA_cm2),
    signedCurrentDensity_uA_cm2: p.potential < 0 ? -p.currentDensity_uA_cm2 : p.currentDensity_uA_cm2,
  }));
  return {
    id: "intersection-offset",
    name: "intersection offset",
    sourceFilename: "fixture.json",
    sourceInstrument: "csv",
    points,
    metadata: {
      electrodeAreaCm2: 1,
      referenceElectrode: "SCE",
      refOffsetVsSHE: 0.241,
      alloyName: "fixture",
      density_g_cm3: 8,
      equivalentWeight: 25.68,
      electrolyte: "synthetic",
      temperatureC: 25,
    },
  } as TafelDataset;
}

test("EUQ-13: the TypeScript intersection limit equals the Python engine's INTERSECTION_MAX_OFFSET_V", () => {
  const py = readFileSync("python/tafel_corrosion_rate_solver.py", "utf8");
  const match = py.match(/^INTERSECTION_MAX_OFFSET_V = ([0-9.]+)$/m);
  assert.ok(match, "python constant INTERSECTION_MAX_OFFSET_V not found");
  assert.equal(Number(match[1]), TAFEL_INTERSECTION_MAX_OFFSET_V);
  assert.equal(fixture.intersectionMaxOffsetV, TAFEL_INTERSECTION_MAX_OFFSET_V);
});

for (const [name, c] of Object.entries(fixture.cases)) {
  test(`EUQ-13: TypeScript fit reproduces the shared fixture (${name})`, () => {
    const fit = tryAutoFitTafel(dataset(c));
    assert.ok(fit.eCorr !== null && fit.iCorr_uA_cm2 !== null);
    assert.ok(Math.abs(fit.eCorr - c.expected.eCorr) < 1e-6, `eCorr ${fit.eCorr}`);
    assert.ok(Math.abs(fit.iCorr_uA_cm2 / c.expected.iCorr_uA_cm2 - 1) < 1e-4, `iCorr ${fit.iCorr_uA_cm2}`);
    assert.equal(fit.intersectionStatus ?? null, c.expected.intersectionStatus);
  });
}
