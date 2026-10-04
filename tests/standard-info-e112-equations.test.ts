import assert from "node:assert/strict";
import test from "node:test";
import { METALLURGICAL_STANDARDS } from "../src/components/StandardInfoIcon";
import { calculateAstmE112FromG } from "../src/utils/metallurgicalConversions";

// The info pop-overs show E112 formulas as text. Until 2026-10 both showed d = 10 * sqrt(2^(1-G)) mm (G 8 -> 884 um,
// about 39x the planimetric 22.45 um). The constants in the new strings are checked here against the E112 definition
// N_AE = 2^(G-1) per in^2 at 100x  =>  N_A = 2^(G-1) * 100^2 / 645.16 per mm^2 at 1x,  planimetric d = 1/sqrt(N_A).
const planimetricDiameterMm = (G: number) => 1 / Math.sqrt((Math.pow(2, G - 1) * 100 ** 2) / 645.16);

test("grain_length: planimetric d = 0.254 sqrt(2^(1-G)) mm and intercept l = 10^(-(G+3.288)/6.643856) mm", () => {
  const eq = METALLURGICAL_STANDARDS.grain_length.equations;
  assert.match(eq, /Planimetric mean diameter d̄ = 0\.254 · √\(2\^\(1-G\)\) mm/);
  assert.match(eq, /Mean lineal intercept ℓ̄ = 10\^\(-\(G \+ 3\.288\)\/6\.643856\) mm/);
  assert.doesNotMatch(eq, /10 · √/);
  // 0.254 = sqrt(645.16 / 100^2) exactly
  assert.ok(Math.abs(Math.sqrt(645.16 / 100 ** 2) - 0.254) < 1e-15);
  for (let G = -3; G <= 16; G += 0.5) {
    assert.ok(Math.abs(0.254 * Math.sqrt(Math.pow(2, 1 - G)) - planimetricDiameterMm(G)) < 1e-12, `G ${G}`);
    // the intercept string is the relation the unit converter displays (rounded to 0.01 um there)
    assert.ok(Math.abs(1000 * Math.pow(10, -(G + 3.288) / 6.643856) - calculateAstmE112FromG(G).meanInterceptUm) <= 0.005 + 1e-9);
  }
  assert.ok(Math.abs(planimetricDiameterMm(8) * 1000 - 22.45) < 0.01);
});

test("hall_petch: d = 254 sqrt(2^(1-G)) um is the same planimetric diameter", () => {
  const eq = METALLURGICAL_STANDARDS.hall_petch.equations;
  assert.match(eq, /d = 254 · √\(2\^\(1-G\)\) µm \(ASTM E112 planimetric diameter\)/);
  assert.doesNotMatch(eq, /10 · √/);
  for (let G = -3; G <= 16; G += 0.5) {
    assert.ok(Math.abs(254 * Math.sqrt(Math.pow(2, 1 - G)) - 1000 * planimetricDiameterMm(G)) < 1e-9, `G ${G}`);
  }
});

// HISTORICAL: the old string's formula at G = 8 gave 884 um (planimetric 22.45 um, intercept 20.0 um).
test("HISTORICAL old pop-over formula d = 10 sqrt(2^(1-G)) mm was ~39x the planimetric diameter", () => {
  const old = (G: number) => 10 * Math.sqrt(Math.pow(2, 1 - G));
  assert.ok(Math.abs(old(8) * 1000 - 883.9) < 0.1);
  assert.ok(Math.abs(old(8) / planimetricDiameterMm(8) - 10 / 0.254) < 1e-9); // 39.37 at every G
});
