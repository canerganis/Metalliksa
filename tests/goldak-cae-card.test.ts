import assert from "node:assert/strict";
import test from "node:test";
import { buildGoldakCaeCard, goldakAbsorbedPower_W, goldakFrontRearFractions, type GoldakCaeCardInput } from "../src/utils/goldakCaeCard";

// Solver-producible keyhole state: IN718, 285 W / 960 mm/s, beam 80 um, layer 40 um, hatch 110 um
// (eta_eff 0.887 > eta_cond 0.38 because H* = 30.8 > 15; goldak-total-power-v2 liquidus extents 17/267/42/108 um;
// seed axes 40/80 um; python/lpbf_thermal_solver.py).
const input = (over: Partial<GoldakCaeCardInput["processParameters"]> = {}): GoldakCaeCardInput => ({
  heatSourceModel: "goldak-total-power-v2",
  material: "Inconel 718",
  baseMetal: "Ni",
  laserWavelength: "IR_1064nm",
  processParameters: {
    laserPower_W: 285,
    scanSpeed_mm_s: 960,
    beamDiameter_um: 80,
    volumetricEnergyDensity_J_mm3: 67.47,
    normalizedEnthalpy: 30.8,
    effectiveAbsorptivity: 0.887,
    conductionAbsorptivity: 0.38,
    ...over,
  },
  meltPoolGeometry: {
    regime: "Keyhole Mode",
    goldakParameters: {
      semiAxis_af_front_um: 17,
      semiAxis_ar_rear_um: 267,
      semiAxis_b_halfwidth_um: 42,
      semiAxis_c_depth_um: 108,
      seed_af_um: 40,
      seed_ar_um: 80,
    },
  },
  solidificationKinetics: {
    thermalGradient_G_K_m: 1.84e7,
    solidificationRate_R_m_s: 0.03,
    coolingRate_K_s: 5.57e5,
    primaryDendriteArmSpacing_PDAS_um: 0.67,
  },
});

const dataLine = (text: string) => {
  const lines = text.split("\n");
  const header = lines.findIndex((l) => l.startsWith("** a_front (m)"));
  assert.ok(header >= 0, "axis header line present");
  return lines[header + 1];
};

test("Q equals laserPower_W * effectiveAbsorptivity (not halved)", () => {
  for (const [P, eta] of [[285, 0.887], [200, 0.357], [95.5, 0.8123]] as const) {
    const { text } = buildGoldakCaeCard(input({ laserPower_W: P, effectiveAbsorptivity: eta }));
    const fields = dataLine(text).trim().split(",").map((f) => Number(f.trim()));
    assert.equal(fields.length, 6);
    assert.ok(Math.abs(fields[4] - P * eta) < 1e-9, `Q ${fields[4]} vs ${P * eta}`);
    assert.equal(fields[5], eta);
  }
  assert.equal(goldakAbsorbedPower_W(140, 0.4), 56);
  assert.equal(goldakAbsorbedPower_W(285, 0.887), 252.795);
});

test("eta_eff field is labelled informational and already included in Q", () => {
  for (const variant of ["thermal-map", "cross-section"] as const) {
    const { text } = buildGoldakCaeCard(input(), variant);
    assert.ok(text.includes("Q_Goldak=eta_eff*P_laser (W, absorbed power deposited in the half-space body; f_f+f_r=2, do not halve), eta_eff (informational, ALREADY included in Q; do not apply again in DFLUX)"));
    assert.ok(!text.includes("Q_total/2"));
    assert.ok(!text.includes("/ 2"));
  }
});

test("f_f and f_r are exported by continuity (0.12 / 1.88 for the IN718 keyhole axes)", () => {
  const { f_f, f_r } = goldakFrontRearFractions(17, 267);
  assert.equal(f_f.toFixed(2), "0.12");
  assert.equal(f_r.toFixed(2), "1.88");
  assert.ok(Math.abs(f_f + f_r - 2) < 1e-12);
  const { text } = buildGoldakCaeCard(input());
  assert.ok(text.includes("** f_f, f_r (continuity rule f_f = 2*a_f/(a_f+a_r), f_r = 2 - f_f): 0.1197, 1.8803"));
  assert.equal(goldakFrontRearFractions(50, 50).f_f, 1);
});

test("card prints the heat source actually used and states the axes are liquidus extents", () => {
  const { text } = buildGoldakCaeCard(input());
  assert.ok(text.includes("** Heat source used by the screening solver: goldak-total-power-v2. *GOLDAK_DOUBLE_ELLIPSOID above is only the TARGET source type of the DFLUX."));
  assert.ok(text.includes("** axes = liquidus extents of the goldak-total-power-v2 screening field (x_front, x_rear, W/2, D incl. keyhole depth), used as UNCALIBRATED Goldak axes"));
  assert.ok(!text.includes("seed axes; not"), "old seed-axes claim removed");
  const rosenthal = buildGoldakCaeCard({ ...input(), heatSourceModel: undefined, modelId: "rosenthal-screening-v1" }).text;
  assert.ok(rosenthal.includes("** axes = liquidus extents of the rosenthal-screening-v1 screening field"));
  const none = buildGoldakCaeCard({ ...input(), heatSourceModel: undefined }).text;
  assert.ok(none.includes("Heat source used by the screening solver: heat source not reported."));
});

test("seed axes are exported on their own reference comment line", () => {
  const { text } = buildGoldakCaeCard(input());
  assert.ok(text.includes("** reference only, not exported below: Goldak seed axes a_front = 40 um, a_rear = 80 um"));
  const base = input();
  const noSeed = buildGoldakCaeCard({
    ...base,
    meltPoolGeometry: { ...base.meltPoolGeometry, goldakParameters: { semiAxis_af_front_um: 17, semiAxis_ar_rear_um: 267, semiAxis_b_halfwidth_um: 42, semiAxis_c_depth_um: 108 } },
  }).text;
  assert.ok(!noSeed.includes("Goldak seed axes"));
});

test("card states that axes and Q are NOT a calibrated pair and prints eta_cond*P", () => {
  for (const variant of ["thermal-map", "cross-section"] as const) {
    const { text } = buildGoldakCaeCard(input(), variant);
    assert.ok(text.includes("** axes and Q are NOT a calibrated pair: the screening field was driven by P_field = P_absorbed/(1+0.55*Stefan)"));
    assert.ok(text.includes("P_field is not exported by the solver and is not recomputed here."));
    assert.ok(text.includes("(eta_eff/eta_cond = 2.33 here; they are equal in conduction cases); an FEA with these axes and Q will not reproduce the screening pool."));
    assert.ok(text.includes("** conduction-field absorbed power before the Stefan factor, eta_cond*P_laser: 108.3 W"));
    assert.ok(text.includes("conductionAbsorptivity (tabulated flat-plate absorptivity, or ray-traced powder value when warp is present; used by the screening conduction field): 0.38"));
    assert.ok(!text.includes("Fresnel"));
  }
});

test("conductionAbsorptivity lines are omitted when the result lacks it, the not-calibrated line stays", () => {
  const { text } = buildGoldakCaeCard(input({ conductionAbsorptivity: undefined }));
  assert.ok(!text.includes("conduction-field absorbed power before the Stefan factor"));
  assert.ok(!text.includes("tabulated flat-plate absorptivity"));
  assert.ok(!text.includes("eta_eff/eta_cond"));
  assert.ok(text.includes("** axes and Q are NOT a calibrated pair"));
  assert.ok(text.includes("can exceed the conduction-field power in transition/keyhole cases"));
});

test("filenames are unchanged per variant", () => {
  assert.equal(buildGoldakCaeCard(input()).filename, "Goldak_LPBF_Inconel_718_285W.inp");
  assert.equal(buildGoldakCaeCard(input(), "thermal-map").filename, "Goldak_LPBF_Inconel_718_285W.inp");
  assert.equal(buildGoldakCaeCard(input(), "cross-section").filename, "Goldak_LPBF_CrossSection_Inconel_718_285W.inp");
});

test("axes are exported in metres with 4-digit exponent format", () => {
  const { text } = buildGoldakCaeCard(input());
  const fields = dataLine(text).trim().split(",").map((f) => f.trim());
  assert.deepEqual(fields.slice(0, 4), ["1.7000e-5", "2.6700e-4", "4.2000e-5", "1.0800e-4"]);
  assert.equal(fields[4], "252.795");
  assert.equal(fields[5], "0.887");
  assert.ok(dataLine(text).startsWith(" "), "data line keeps its leading space");
});

test("unchanged card lines stay verbatim; only the enthalpy line differs by variant", () => {
  const map = buildGoldakCaeCard(input(), "thermal-map").text;
  const cross = buildGoldakCaeCard(input(), "cross-section").text;
  const rule = "** -------------------------------------------------------------";
  for (const text of [map, cross]) {
    assert.ok(text.startsWith(`${rule}\n** METALLIX LPBF GOLDAK HEAT SOURCE CAE EXPORT CARD\n`));
    assert.ok(text.includes("** Material: Inconel 718 (Base: Ni)\n** Laser Power: 285 W | Scan Speed: 960 mm/s\n** Beam Diameter: 80 um | Wavelength: IR_1064nm\n** Volumetric Energy Density (VED): 67.47 J/mm3\n"));
    assert.ok(text.includes("*DFLUX, USER\n*GOLDAK_DOUBLE_ELLIPSOID\n"));
    assert.ok(text.includes("** Solidification Kinetics:\n** G_avg: 18400000 K/m\n** R_solid: 0.03 m/s\n** Cooling Rate: 557000 K/s\n** Primary Spacing (PDAS): 0.67 um\n" + rule));
    assert.ok(text.endsWith(rule));
  }
  assert.ok(!map.includes("Normalized Enthalpy"));
  assert.ok(map.includes("** Parameters in meters (SI Units):"));
  assert.ok(cross.includes("** Normalized Enthalpy (ΔH/hs): 30.8 (Keyhole Mode)"));
  assert.ok(cross.includes("** Semi-Axes in meters (SI Units):"));
});
