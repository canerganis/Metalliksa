// Goldak double-ellipsoid CAE export card (Abaqus-style DFLUX text) shared by the LPBF melt pool views.
//
// Power normalisation: with f_f + f_r = 2 the Goldak double ellipsoid integrates to Q over the half-space body
// (z >= 0). In an FEA half-space model Q is therefore the ABSORBED power deposited in the part, Q = eta_eff * P_laser.
// It must not be halved.
//
// The exported semi-axes are NOT seed axes and NOT a calibrated Goldak fit: they are the liquidus-isotherm extents of
// the screening field the solver ran (x_front, x_rear, W/2, D including keyhole depth;
// python/lpbf_thermal_solver.py meltPoolGeometry.goldakParameters), whichever heat source the request used
// (heatSourceModel / modelId of the result). The seed axes are the separate seed_af_um / seed_ar_um fields. Axes and Q
// are not a calibrated pair (see the card text).

export type GoldakCardVariant = "thermal-map" | "cross-section";

export interface GoldakCaeCardInput {
  /** Heat source the solver actually used (Python result); the view may not have requested Goldak. */
  heatSourceModel?: string;
  modelId?: string;
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
    /** Liquidus extents of the screening field (a_f, a_r, b = W/2, c = D); seed_* are the separate Goldak seed axes. */
    goldakParameters: {
      semiAxis_af_front_um: number;
      semiAxis_ar_rear_um: number;
      semiAxis_b_halfwidth_um: number;
      semiAxis_c_depth_um: number;
      seed_af_um?: number;
      seed_ar_um?: number;
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

/**
 * Goldak continuity weights for a double ellipsoid with front/rear semi-axes a_f, a_r: f_f/a_f = f_r/a_r matched at the
 * source centre gives f_f = 2*a_f/(a_f + a_r), f_r = 2 - f_f (so f_f + f_r = 2).
 */
export const goldakFrontRearFractions = (a_front: number, a_rear: number): { f_f: number; f_r: number } => {
  const f_f = (2 * a_front) / (a_front + a_rear);
  return { f_f, f_r: 2 - f_f };
};

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
  const heatSource = pyResult.heatSourceModel ?? pyResult.modelId ?? "heat source not reported";
  const { f_f, f_r } = goldakFrontRearFractions(goldak.semiAxis_af_front_um, goldak.semiAxis_ar_rear_um);
  const etaCond = params.conductionAbsorptivity;
  const hasEtaCond = etaCond !== undefined && etaCond !== null;

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
    "** Screening-model output; not Goldak FEA, not validated (see docs/LPBF_ENGINEERING.md).",
    `** Heat source used by the screening solver: ${heatSource}. *GOLDAK_DOUBLE_ELLIPSOID above is only the TARGET source type of the DFLUX.`,
    `** axes = liquidus extents of the ${heatSource} screening field (x_front, x_rear, W/2, D incl. keyhole depth), used as UNCALIBRATED Goldak axes`,
  );
  if (goldak.seed_af_um !== undefined && goldak.seed_ar_um !== undefined) {
    lines.push(`** reference only, not exported below: Goldak seed axes a_front = ${goldak.seed_af_um} um, a_rear = ${goldak.seed_ar_um} um`);
  }
  if (hasEtaCond) {
    lines.push(
      `** conductionAbsorptivity (tabulated flat-plate absorptivity, or ray-traced powder value when warp is present; used by the screening conduction field): ${etaCond}`,
      `** conduction-field absorbed power before the Stefan factor, eta_cond*P_laser: ${goldakAbsorbedPower_W(params.laserPower_W, etaCond)} W`,
    );
  }
  lines.push(
    "** axes and Q are NOT a calibrated pair: the screening field was driven by P_field = P_absorbed/(1+0.55*Stefan), with P_absorbed = conductionAbsorptivity*P_laser for goldak/eagar-tsai sources and effectiveAbsorptivity*P_laser for rosenthal (python/lpbf_thermal_solver.py); P_field is not exported by the solver and is not recomputed here.",
    hasEtaCond
      ? `** Q = eta_eff*P_laser exceeds the conduction-field power in transition/keyhole cases (eta_eff/eta_cond = ${(params.effectiveAbsorptivity / (etaCond as number)).toFixed(2)} here; they are equal in conduction cases); an FEA with these axes and Q will not reproduce the screening pool.`
      : "** Q = eta_eff*P_laser can exceed the conduction-field power in transition/keyhole cases; an FEA with these axes and Q will not reproduce the screening pool.",
    "** a_front (m), a_rear (m), b_halfwidth (m), c_depth (m), Q_Goldak=eta_eff*P_laser (W, absorbed power deposited in the half-space body; f_f+f_r=2, do not halve), eta_eff (informational, ALREADY included in Q; do not apply again in DFLUX)",
    ` ${axis_m(goldak.semiAxis_af_front_um)}, ${axis_m(goldak.semiAxis_ar_rear_um)}, ${axis_m(goldak.semiAxis_b_halfwidth_um)}, ${axis_m(goldak.semiAxis_c_depth_um)}, ${Q_W}, ${params.effectiveAbsorptivity}`,
    `** f_f, f_r (continuity rule f_f = 2*a_f/(a_f+a_r), f_r = 2 - f_f): ${f_f.toFixed(4)}, ${f_r.toFixed(4)}`,
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
