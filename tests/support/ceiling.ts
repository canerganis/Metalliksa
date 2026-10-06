// Shrink-only allowlists (Phase 7 slice 1 fix round). Each live allowlist has a committed
// *.ceiling.json capping it: the live entries must be a subset of the ceiling's lists, and a
// ceiling may itself only shrink (python/test_allowlist_ceilings.py pins its content; any edit
// needs a 'Ceiling-Review:' commit trailer, see scripts/check_ceiling_review.py). Site-keyed
// entries ('USE /api/x (routes/a.ts#2)') are capped by path in a list plus a per-path site
// count (readCeilingCounts). Adding an allowlist entry therefore needs a reviewed ceiling edit.
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

/** A `{ entry: maxCount }` map of a ceiling (non-negative integers). */
export function readCeilingCounts(relative: string, key: string): ReadonlyMap<string, number> {
  const data = JSON.parse(readFileSync(path.join(repoRoot, relative), 'utf8')) as Record<string, unknown>;
  const values = data[key];
  if (!values || typeof values !== 'object' || Array.isArray(values)
    || !Object.values(values).every(value => Number.isInteger(value) && (value as number) >= 0)) {
    throw new Error(`${relative}: ${key} must map entries to non-negative integer counts`);
  }
  return new Map(Object.entries(values as Record<string, number>));
}

/** Entries of the live allowlist that the immutable ceiling does not allow. */
export function beyondCeiling(current: Iterable<string>, ceiling: ReadonlySet<string>): string[] {
  return [...current].filter(entry => !ceiling.has(entry)).sort();
}

/** Paths whose number of live site-keyed entries exceeds the ceiling's count (missing = 0). */
export function beyondSiteCounts(current: Iterable<string>, pathOf: (key: string) => string, counts: ReadonlyMap<string, number>): string[] {
  const seen = new Map<string, number>();
  for (const key of current) seen.set(pathOf(key), (seen.get(pathOf(key)) ?? 0) + 1);
  return [...seen].filter(([entry, count]) => count > (counts.get(entry) ?? 0)).map(([entry, count]) => `${entry} (${count} > ${counts.get(entry) ?? 0} sites)`).sort();
}
