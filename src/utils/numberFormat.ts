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

/**
 * en-US grouping with exactly the digits String(value) shows: no rounding, so a raw input value such as
 * 1200 or 0.0005 reads "1,200" / "0.0005". String() gives the shortest round-trip decimal; ICU rounding the
 * same double to that many fraction digits yields the same digits. Exponent forms, non-finite values, -0
 * and more than 20 fraction digits (the portable maximumFractionDigits limit) are returned as String() shows them.
 */
export function formatExactNumber(value: number): string {
  const text = String(value);
  const digits = text.split(".")[1]?.length ?? 0;
  if (!Number.isFinite(value) || value === 0 || digits > 20 || /e/i.test(text)) return text;
  return value.toLocaleString(DISPLAY_LOCALE, { maximumFractionDigits: digits });
}
