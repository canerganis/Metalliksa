import { availableProperty } from "./compositionPropertyAvailability";

/** Screening ratio the decision lab compares the stress proxy against: 0.7 x Rp0.2. Not an acceptance criterion. */
export const STRESS_PROXY_YIELD_FRACTION = 0.7;

export type StressProxyYieldCheck =
  | { status: "unavailable"; ok: null; limit_MPa: null; hint: string }
  | { status: "below" | "at-or-above"; ok: boolean; limit_MPa: number; hint: string };

/**
 * Compares the Python stress proxy with 0.7 x Rp0.2 only when a real yield strength is supplied. The shared specimen
 * carries none (the composition heuristic was removed), so with its value this reports "unavailable": no pass/fail.
 */
export function stressProxyYieldCheck(stressProxy_MPa: number, yieldStrength_MPa: number | null | undefined): StressProxyYieldCheck {
  const yieldMpa = availableProperty(yieldStrength_MPa);
  if (yieldMpa === null || !Number.isFinite(stressProxy_MPa)) {
    return {
      status: "unavailable",
      ok: null,
      limit_MPa: null,
      hint: "No pass/fail: Rp0.2 unavailable (not computed from composition)",
    };
  }
  const limit_MPa = Math.round(yieldMpa * STRESS_PROXY_YIELD_FRACTION);
  const ok = stressProxy_MPa < yieldMpa * STRESS_PROXY_YIELD_FRACTION;
  return { status: ok ? "below" : "at-or-above", ok, limit_MPa, hint: `< 0.7 Rp0.2 (${limit_MPa})` };
}
