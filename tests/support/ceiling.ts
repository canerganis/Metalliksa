// Shrink-only allowlists (Phase 7 slice 1 fix round). Each live allowlist has a committed
// *.ceiling.json holding the immutable initial allowance; the live entries must be a subset.
// Adding an allowlist entry therefore needs an explicit, reviewable edit of the ceiling file.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { repoRoot } from './importGraph';

export function readCeiling<K extends string>(relative: string, ...keys: K[]): Record<K, Set<string>> {
  const data = JSON.parse(readFileSync(path.join(repoRoot, relative), 'utf8')) as Record<string, unknown>;
  const result = {} as Record<K, Set<string>>;
  for (const key of keys) {
    const values = data[key];
    if (!Array.isArray(values) || !values.every(value => typeof value === 'string')) throw new Error(`${relative}: ${key} must be a string array`);
    result[key] = new Set(values as string[]);
  }
  return result;
}

/** Entries of the live allowlist that the immutable ceiling does not allow. */
export function beyondCeiling(current: Iterable<string>, ceiling: ReadonlySet<string>): string[] {
  return [...current].filter(entry => !ceiling.has(entry)).sort();
}
