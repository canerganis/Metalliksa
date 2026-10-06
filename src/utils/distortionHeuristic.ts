/**
 * Plain-language label for the residual-stress / distortion screening values returned in
 * defectDiagnostics by python/lpbf_thermal_solver.py (frozen solver; the formula is documented
 * here, not changed). The constants below are the solver's fixed, uncited factors.
 */
export const DISTORTION_HEURISTIC_CONSTANTS = {
  stressKnockdown: 0.72,
  referenceLayer_um: 40,
  indexScale_MPa: 420,
  recoaterModerateIndex: 1.2,
  recoaterHighIndex: 2.0,
} as const;

export const DISTORTION_HEURISTIC_NOTE =
  "Heuristic, not a stress or distortion solve: σ_eff = 0.72 · E·α·(T_solidus − T_preheat) / (1 − ν); " +
  "distortion index = σ_eff · (layer thickness / 40 µm) / 420 MPa; recoater-risk bands at index 1.2 and 2.0. " +
  "The 0.72, 40 µm, 420 MPa and band values are fixed uncited constants in the solver.";
