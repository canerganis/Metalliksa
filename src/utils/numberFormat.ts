/**
 * One display locale for formatted numbers, independent of the browser locale.
 * en-US: comma groups thousands, point marks decimals ("1,200 mm/s", "31.25 J/mm³"), matching the
 * en-US formatting already used for step counts and result values. Only the presentation changes:
 * the same rounding (maximumFractionDigits) is applied to the same value.
 */
export const DISPLAY_LOCALE = "en-US";

export function formatDisplayNumber(value: number, maximumFractionDigits = 1): string {
  return value.toLocaleString(DISPLAY_LOCALE, { maximumFractionDigits });
}
