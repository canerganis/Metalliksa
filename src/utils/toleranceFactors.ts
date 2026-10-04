/**
 * One-sided normal tolerance factors used by the A/B-basis SCREENING estimates of
 * AerospaceAuditReportGenerator and StandardQualificationEngine (shared so the two screens cannot drift).
 *
 * For 5 <= N <= EXACT_K_LAST_N (300) k is the EXACT factor nct.ppf(0.95, N-1, z_p sqrt(N)) / sqrt(N) from the generated
 * table (toleranceFactorTable.ts), rounded UP to 3 decimals so the displayed k is never below the exact value.
 * A non-integer N uses the table row of floor(N) (fewer coupons -> larger, conservative k).
 *
 * Above the table (and below N = 5, which no caller reaches: both screens clamp N >= 10) the Natrella /
 * Lieberman-Resnikoff closed form is used: k is the larger root of
 *   a k^2 - 2 z_p k + b = 0,   a = 1 - z_g^2 / (2(N-1)),   b = z_p^2 - z_g^2 / N,
 * i.e. k = (z_p + sqrt(z_p^2 - a b)) / a, rounded to 3 decimals. It is slightly below the exact value (optimistic):
 * 1.0 % (A) / 1.4 % (B) at N = 10, 0.44 % / 0.53 % at N = 31, 0.035 % / 0.064 % at N = 300, which is why the exact table
 * covers N <= 300. Screening estimates only, not MMPDS handbook allowables.
 */

import { EXACT_K_A, EXACT_K_B, EXACT_K_FIRST_N, EXACT_K_LAST_N } from "./toleranceFactorTable";

const Z99 = 2.326348; // A-basis: 99 % content
const Z90 = 1.281552; // B-basis: 90 % content
const Z95_CONF = 1.644854; // 95 % confidence

/** Natrella one-sided tolerance factor rounded to 3 decimals. N is used as given. */
export function natrellaOneSidedToleranceFactor(zP: number, N: number): number {
  return (
    Number(
      (
        (zP +
          Math.sqrt(
            zP * zP -
              (1 - (Z95_CONF * Z95_CONF) / (2 * (N - 1))) *
                (zP * zP - (Z95_CONF * Z95_CONF) / N)
          )) /
        (1 - (Z95_CONF * Z95_CONF) / (2 * (N - 1)))
      ).toFixed(3)
    ) || Number((zP * (1 + Z95_CONF / Math.sqrt(2 * N))).toFixed(3))
  );
}

/** Round up to 3 decimals (conservative display of a tolerance factor). */
function ceil3(k: number): number {
  return Math.ceil(k * 1000) / 1000;
}

/** Table row for N, or undefined outside [EXACT_K_FIRST_N, EXACT_K_LAST_N] (or for a non-finite N). */
function exactRow(N: number): number | undefined {
  if (!Number.isFinite(N)) return undefined;
  const n = Math.floor(N);
  if (n < EXACT_K_FIRST_N || n > EXACT_K_LAST_N) return undefined;
  return n - EXACT_K_FIRST_N;
}

/** Short name of the method screeningToleranceFactors uses for a screen's (clamped, N >= 10) sample size, for report text. */
export function toleranceFactorMethodLabel(sampleSizeN: number): string {
  return exactRow(Math.max(10, sampleSizeN)) !== undefined ? "exact noncentral-t" : "Lieberman-Resnikoff";
}

/** k_A (99 % content / 95 % confidence) and k_B (90 % / 95 %) for sample size N. */
export function screeningToleranceFactors(N: number): { kA: number; kB: number } {
  const row = exactRow(N);
  if (row !== undefined) return { kA: ceil3(EXACT_K_A[row]), kB: ceil3(EXACT_K_B[row]) };
  return { kA: natrellaOneSidedToleranceFactor(Z99, N), kB: natrellaOneSidedToleranceFactor(Z90, N) };
}
