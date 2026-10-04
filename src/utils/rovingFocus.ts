/**
 * Roving focus for a vertical list that is a single Tab stop (the module navigation).
 * Returns the index to focus for `key`, or null when the key is not a navigation key.
 * `current` is -1 when focus is outside the list. Up/Down wrap; Home/End jump to the ends.
 */
export function rovingIndex(count: number, current: number, key: string): number | null {
  if (count <= 0) return null;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  if (key === "ArrowDown") return current < 0 || current >= count - 1 ? 0 : current + 1;
  if (key === "ArrowUp") return current <= 0 ? count - 1 : current - 1;
  return null;
}
