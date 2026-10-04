/**
 * One-sided normal tolerance factors used by the A/B-basis SCREENING estimates of
 * AerospaceAuditReportGenerator and StandardQualificationEngine (shared so the two screens cannot drift).
 *
 * Natrella / Lieberman-Resnikoff closed-form approximation: k is the larger root of
 *   a k^2 - 2 z_p k + b = 0,   a = 1 - z_g^2 / (2(N-1)),   b = z_p^2 - z_g^2 / N,
 * i.e. k = (z_p + sqrt(z_p^2 - a b)) / a.
 * It approximates the exact factor nct.ppf(gamma, N-1, z_p sqrt(N)) / sqrt(N); against that exact value it is
 * slightly low (optimistic) at small N: about 1.0 % (A) / 1.4 % (B) at N = 10, under 1 % for N >= 11 (A) and
 * N >= 16 (B). See tests/fixtures/one-sided-tolerance-factor-oracle.json. Screening estimates only, not MMPDS
 * handbook allowables.
 *
 * The expression and rounding (toFixed(3)) are the ones AerospaceAuditReportGenerator has always used, kept
 * bit-identical.
 */

const Z99 = 2.326348; // A-basis: 99 % content
const Z90 = 1.281552; // B-basis: 90 % content
const Z95_CONF = 1.644854; // 95 % confidence

/** Natrella one-sided tolerance factor rounded to 3 decimals (as displayed). N is used as given (callers clamp N >= 10). */
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

/** k_A (99 % content / 95 % confidence) and k_B (90 % / 95 %) for sample size N. */
export function screeningToleranceFactors(N: number): { kA: number; kB: number } {
  return { kA: natrellaOneSidedToleranceFactor(Z99, N), kB: natrellaOneSidedToleranceFactor(Z90, N) };
}
