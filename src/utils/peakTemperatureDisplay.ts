// Wave B D1/D10: how the reported melt-pool peak temperature is labelled and how far colour scales may use it.
import type { PythonLPBFResult } from "../services/pythonComputationService";

/**
 * Top of the melt-pool colour scale (Wave B D10). The reported peak is the beam-centre value T(0,0,0) of a conduction
 * field without an evaporation sink; for Rosenthal after LA-2 it is the regularised singular-source value
 * T0 + P/(2 pi k r_reg), often 3-5e4 C. Using it as the scale top would compress every colour band into the liquidus
 * shell, so the scale is capped at max(T_vap, 1.5 * liquidus). surfaceTemperature_C = min(peak, T_vap), so when the
 * peak exceeds T_vap it carries T_vap. The true peak is still shown as text with its basis label.
 * Results without surfaceTemperature_C (archived pre-Tier-2 payloads) fall back to FALLBACK_VAPOR_CAP_C, a display-only
 * bound above the normal boiling point of every alloy base the app models (Ti about 3287 C is the highest).
 */
export const FALLBACK_VAPOR_CAP_C = 3500;

export function colourScalePeak_C(result: Pick<PythonLPBFResult, "hydrodynamicsAndRecoil">, liquidus_C: number): number {
  const h = result.hydrodynamicsAndRecoil;
  const peak = h.peakTemperature_C;
  const vaporCap = typeof h.surfaceTemperature_C === "number" && Number.isFinite(h.surfaceTemperature_C) ? h.surfaceTemperature_C : FALLBACK_VAPOR_CAP_C;
  return Math.min(peak, Math.max(vaporCap, 1.5 * liquidus_C));
}

/** Short text for the peak-temperature basis (Wave B D1); null for older results without the label. */
export function peakTemperatureBasisLabel(result: Pick<PythonLPBFResult, "hydrodynamicsAndRecoil">): string | null {
  switch (result.hydrodynamicsAndRecoil.peakTemperatureBasis) {
    case "regularised-singular-source-value":
      return "regularised point-source centre value, not a wall temperature";
    case "distributed-source-conduction-centre-value":
      return "uncapped conduction-field centre value, not a wall temperature";
    default:
      return null;
  }
}
