import assert from "node:assert/strict";
import { test } from "node:test";
import { isLoftKeyhole, LOFT_KEYHOLE_DH_HS_EDGE } from "../src/components/3d-distortion-lab/meltPool3DGeometry";
import { keyholeGateOk } from "../src/components/3d-distortion-lab/IndustrialLPBFDecisionLab";

const mk = (regime: string, dh?: number) =>
  ({ meltPoolGeometry: { regime }, processParameters: dh === undefined ? {} : { normalizedEnthalpy: dh } }) as never;

test("loft keyhole shape follows the legacy ΔH/hs 30 contour edge, not the regime label", () => {
  assert.equal(LOFT_KEYHOLE_DH_HS_EDGE, 30);
  assert.equal(isLoftKeyhole(mk("Keyhole", 25)), false); // regime Keyhole from 20, contour edge still 30
  assert.equal(isLoftKeyhole(mk("Keyhole", 30)), true);
  assert.equal(isLoftKeyhole(mk("Conduction", 45)), true);
});

test("loft keyhole falls back to the regime label when ΔH/hs is missing", () => {
  assert.equal(isLoftKeyhole(mk("Keyhole")), true);
  assert.equal(isLoftKeyhole(mk("Conduction")), false);
});

test("missing keyhole gate verdict is unavailable (null), not OK", () => {
  assert.equal(keyholeGateOk(undefined), null);
  assert.equal(keyholeGateOk("pass"), true);
  assert.equal(keyholeGateOk("advisory"), true);
  assert.equal(keyholeGateOk("fail"), false);
});
