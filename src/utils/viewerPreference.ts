/**
 * Per-viewer UI conveniences kept in localStorage (a remembered choice in a select).
 * Never results, jobs, evidence or validation state. Storage may be missing, blocked or hold a value
 * from another build: every read is checked against the allowed values and falls back silently.
 */
type ChoiceStorage = Pick<Storage, "getItem" | "setItem">;

function defaultStorage(): ChoiceStorage | undefined {
  return typeof localStorage === "undefined" ? undefined : localStorage;
}

export function readChoice<T extends string>(key: string, allowed: readonly T[], fallback: T, storage?: ChoiceStorage): T {
  try {
    const value = (storage ?? defaultStorage())?.getItem(key);
    return allowed.includes(value as T) ? (value as T) : fallback;
  } catch {
    return fallback;
  }
}

export function writeChoice(key: string, value: string, storage?: ChoiceStorage): void {
  try {
    (storage ?? defaultStorage())?.setItem(key, value);
  } catch {
    /* The choice still applies for this page view. */
  }
}
