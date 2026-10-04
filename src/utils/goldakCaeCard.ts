// Goldak double-ellipsoid CAE export card (Abaqus-style DFLUX text) shared by the LPBF melt pool views.
//
// Power normalisation: with f_f + f_r = 2 the Goldak double ellipsoid integrates to Q over the half-space body
// (z >= 0). In an FEA half-space model Q is therefore the ABSORBED power deposited in the part, Q = eta_eff * P_laser.
// It must not be halved. The semi-axes are the screening-model seed axes (python/lpbf_thermal_solver.py), not a
// calibrated or validated Goldak FEA fit.

export type GoldakCardVariant = "thermal-map" | "cross-section";

export interface GoldakCaeCardInput {
  material: string;
  baseMetal: string;
  laserWavelength: string;
  processParameters: {
    laserPower_W: number;
    scanSpeed_mm_s: number;
    beamDiameter_um: number;
    volumetricEnergyDensity_J_mm3: number;
    normalizedEnthalpy?: number;
    effectiveAbsorptivity: number;
    conductionAbsorptivity?: number;
  };
  meltPoolGeometry: {
    regime?: string;
    goldakParameters: {
      semiAxis_af_front_um: number;
      semiAxis_ar_rear_um: number;
      semiAxis_b_halfwidth_um: number;
      semiAxis_c_depth_um: number;
    };
  };
  solidificationKinetics: {
    thermalGradient_G_K_m: number;
    solidificationRate_R_m_s: number;
    coolingRate_K_s: number;
    primaryDendriteArmSpacing_PDAS_um: number;
  };
}

export interface GoldakCaeCard {
  filename: string;
  text: string;
}

const RULE = "** -------------------------------------------------------------";

/** Absorbed power Q = eta_eff * P_laser in W (cleaned of binary floating-point noise, 15 significant digits). */
export const goldakAbsorbedPower_W = (laserPower_W: number, effectiveAbsorptivity: number): number =>
  Number((laserPower_W * effectiveAbsorptivity).toPrecision(15));

export function buildGoldakCaeCard(
  pyResult: GoldakCaeCardInput,
  variant: GoldakCardVariant = "thermal-map",
): GoldakCaeCard {
  const params = pyResult.processParameters;
  const geom = pyResult.meltPoolGeometry;
  const goldak = geom.goldakParameters;
  const kin = pyResult.solidificationKinetics;
  const crossSection = variant === "cross-section";
  const axis_m = (um: number) => (um * 1e-6).toExponential(4);
  const Q_W = goldakAbsorbedPower_W(params.laserPower_W, params.effectiveAbsorptivity);

  const lines: string[] = [
    RULE,
    "** METALLIX LPBF GOLDAK HEAT SOURCE CAE EXPORT CARD",
    `** Material: ${pyResult.material} (Base: ${pyResult.baseMetal})`,
    `** Laser Power: ${params.laserPower_W} W | Scan Speed: ${params.scanSpeed_mm_s} mm/s`,
    `** Beam Diameter: ${params.beamDiameter_um} um | Wavelength: ${pyResult.laserWavelength}`,
    `** Volumetric Energy Density (VED): ${params.volumetricEnergyDensity_J_mm3} J/mm3`,
  ];
  if (crossSection) lines.push(`** Normalized Enthalpy (ΔH/hs): ${params.normalizedEnthalpy} (${geom.regime})`);
  lines.push(
    RULE,
    "*DFLUX, USER",
    "*GOLDAK_DOUBLE_ELLIPSOID",
    crossSection ? "** Semi-Axes in meters (SI Units):" : "** Parameters in meters (SI Units):",
    "** Screening-model seed axes; not Goldak FEA, not validated (see docs/LPBF_ENGINEERING.md).",
  );
  if (params.conductionAbsorptivity !== undefined && params.conductionAbsorptivity !== null) {
    lines.push(`** conductionAbsorptivity (Fresnel A used by the screening conduction field): ${params.conductionAbsorptivity}`);
  }
  lines.push(
    "** a_front (m), a_rear (m), b_halfwidth (m), c_depth (m), Q_Goldak=eta_eff*P_laser (W, absorbed power deposited in the half-space body; f_f+f_r=2, do not halve), eta_eff",
    ` ${axis_m(goldak.semiAxis_af_front_um)}, ${axis_m(goldak.semiAxis_ar_rear_um)}, ${axis_m(goldak.semiAxis_b_halfwidth_um)}, ${axis_m(goldak.semiAxis_c_depth_um)}, ${Q_W}, ${params.effectiveAbsorptivity}`,
    "** Solidification Kinetics:",
    `** G_avg: ${kin.thermalGradient_G_K_m} K/m`,
    `** R_solid: ${kin.solidificationRate_R_m_s} m/s`,
    `** Cooling Rate: ${kin.coolingRate_K_s} K/s`,
    `** Primary Spacing (PDAS): ${kin.primaryDendriteArmSpacing_PDAS_um} um`,
    RULE,
  );

  const material = pyResult.material.replace(/\s+/g, "_");
  const filename = `Goldak_LPBF_${crossSection ? "CrossSection_" : ""}${material}_${params.laserPower_W}W.inp`;
  return { filename, text: lines.join("\n") };
}
