import assert from "node:assert/strict";
import test from "node:test";
import { buildGoldakCaeCard, goldakAbsorbedPower_W, type GoldakCaeCardInput } from "../src/utils/goldakCaeCard";

const input = (over: Partial<GoldakCaeCardInput["processParameters"]> = {}): GoldakCaeCardInput => ({
  material: "IN718 Test",
  baseMetal: "Ni",
  laserWavelength: "1070 nm",
  processParameters: {
    laserPower_W: 140,
    scanSpeed_mm_s: 900,
    beamDiameter_um: 80,
    volumetricEnergyDensity_J_mm3: 64.8,
    normalizedEnthalpy: 11.2,
    effectiveAbsorptivity: 0.4,
    conductionAbsorptivity: 0.37,
    ...over,
  },
  meltPoolGeometry: {
    regime: "conduction",
    goldakParameters: {
      semiAxis_af_front_um: 40,
      semiAxis_ar_rear_um: 120.5,
      semiAxis_b_halfwidth_um: 55.25,
      semiAxis_c_depth_um: 33,
    },
  },
  solidificationKinetics: {
    thermalGradient_G_K_m: 1.2e6,
    solidificationRate_R_m_s: 0.3,
    coolingRate_K_s: 3.6e5,
    primaryDendriteArmSpacing_PDAS_um: 0.4,
  },
});

const dataLine = (text: string) => {
  const lines = text.split("\n");
  const header = lines.findIndex((l) => l.startsWith("** a_front (m)"));
  assert.ok(header >= 0, "axis header line present");
  return lines[header + 1];
};

test("Q equals laserPower_W * effectiveAbsorptivity (not halved)", () => {
  for (const [P, eta] of [[140, 0.4], [200, 0.357], [95.5, 0.8123]] as const) {
    const { text } = buildGoldakCaeCard(input({ laserPower_W: P, effectiveAbsorptivity: eta }));
    const fields = dataLine(text).trim().split(",").map((f) => Number(f.trim()));
    assert.equal(fields.length, 6);
    assert.ok(Math.abs(fields[4] - P * eta) < 1e-9, `Q ${fields[4]} vs ${P * eta}`);
    assert.equal(fields[5], eta);
  }
  assert.equal(goldakAbsorbedPower_W(140, 0.4), 56);
});

test("card text states the half-space normalisation and no longer halves Q", () => {
  for (const variant of ["thermal-map", "cross-section"] as const) {
    const { text } = buildGoldakCaeCard(input(), variant);
    assert.ok(text.includes("do not halve"));
    assert.ok(text.includes("Q_Goldak=eta_eff*P_laser (W, absorbed power deposited in the half-space body; f_f+f_r=2, do not halve), eta_eff"));
    assert.ok(!text.includes("Q_total/2"));
    assert.ok(!text.includes("/ 2"));
    assert.ok(text.includes("** Screening-model seed axes; not Goldak FEA, not validated (see docs/LPBF_ENGINEERING.md)."));
    assert.ok(text.includes("** conductionAbsorptivity (Fresnel A used by the screening conduction field): 0.37"));
  }
});

test("conductionAbsorptivity line is omitted when the result lacks it", () => {
  const { text } = buildGoldakCaeCard(input({ conductionAbsorptivity: undefined }));
  assert.ok(!text.includes("conductionAbsorptivity"));
});

test("filenames are unchanged per variant", () => {
  assert.equal(buildGoldakCaeCard(input()).filename, "Goldak_LPBF_IN718_Test_140W.inp");
  assert.equal(buildGoldakCaeCard(input(), "thermal-map").filename, "Goldak_LPBF_IN718_Test_140W.inp");
  assert.equal(buildGoldakCaeCard(input(), "cross-section").filename, "Goldak_LPBF_CrossSection_IN718_Test_140W.inp");
});

test("axes are exported in metres with 4-digit exponent format", () => {
  const { text } = buildGoldakCaeCard(input());
  const fields = dataLine(text).trim().split(",").map((f) => f.trim());
  assert.deepEqual(fields.slice(0, 4), ["4.0000e-5", "1.2050e-4", "5.5250e-5", "3.3000e-5"]);
  assert.ok(dataLine(text).startsWith(" "), "data line keeps its leading space");
});

test("unchanged card lines stay verbatim; only the enthalpy line differs by variant", () => {
  const map = buildGoldakCaeCard(input(), "thermal-map").text;
  const cross = buildGoldakCaeCard(input(), "cross-section").text;
  const rule = "** -------------------------------------------------------------";
  for (const text of [map, cross]) {
    assert.ok(text.startsWith(`${rule}\n** METALLIX LPBF GOLDAK HEAT SOURCE CAE EXPORT CARD\n`));
    assert.ok(text.includes("** Material: IN718 Test (Base: Ni)\n** Laser Power: 140 W | Scan Speed: 900 mm/s\n** Beam Diameter: 80 um | Wavelength: 1070 nm\n** Volumetric Energy Density (VED): 64.8 J/mm3\n"));
    assert.ok(text.includes("*DFLUX, USER\n*GOLDAK_DOUBLE_ELLIPSOID\n"));
    assert.ok(text.includes("** Solidification Kinetics:\n** G_avg: 1200000 K/m\n** R_solid: 0.3 m/s\n** Cooling Rate: 360000 K/s\n** Primary Spacing (PDAS): 0.4 um\n" + rule));
    assert.ok(text.endsWith(rule));
  }
  assert.ok(!map.includes("Normalized Enthalpy"));
  assert.ok(map.includes("** Parameters in meters (SI Units):"));
  assert.ok(cross.includes("** Normalized Enthalpy (ΔH/hs): 11.2 (conduction)"));
  assert.ok(cross.includes("** Semi-Axes in meters (SI Units):"));
});
