/**
 * Pure filtering and ranking for the command palette (Phase 9 shell, DESIGN-9 section 3).
 *
 * The palette lists the navigation modules derived from the module registry (MODULES in
 * src/data/workspaces.ts); this file only orders them for a query and never adds, drops or relabels
 * an entry. Every query token must match one field of an entry, otherwise the entry is left out.
 * Equal scores keep registry (navigation) order, so an empty query shows the sidebar order.
 */
import { rovingIndex } from './rovingFocus';

export interface PaletteEntry {
  readonly id: string;
  readonly label: string;
  readonly description: string;
  readonly scope: string;
  readonly workspaceLabel: string;
}

/** Lower case without diacritics (and dotless i folded to i), so "alasim" finds "Alaşım". */
export function normalizeForSearch(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/ı/g, 'i');
}

const isWordStart = (text: string, index: number) => index === 0 || !/[a-z0-9]/.test(text[index - 1]);

/**
 * Subsequence match of `token` in `text` (both normalized). Returns null when some character is
 * missing; otherwise a score that rewards consecutive characters and characters at word starts.
 */
export function subsequenceScore(text: string, token: string): number | null {
  if (!token) return 0;
  let score = 0;
  let from = 0;
  let previous = -2;
  for (const char of token) {
    const index = text.indexOf(char, from);
    if (index === -1) return null;
    score += 1;
    if (index === previous + 1) score += 3;
    if (isWordStart(text, index)) score += 2;
    previous = index;
    from = index + 1;
  }
  return score;
}

/** Best score of one token against one entry, or null when no field matches. */
function tokenScore(entry: PaletteEntry, token: string): number | null {
  const label = normalizeForSearch(entry.label);
  const at = label.indexOf(token);
  if (at === 0) return 120;
  if (at > 0 && isWordStart(label, at)) return 100;
  if (at > 0) return 80;
  if (normalizeForSearch(entry.id).includes(token)) return 60;
  if (normalizeForSearch(entry.workspaceLabel).includes(token) || normalizeForSearch(entry.scope).includes(token)) return 40;
  // Description words count only from two characters on, so a single letter does not match every entry.
  if (token.length >= 2 && normalizeForSearch(entry.description).includes(token)) return 20;
  const fuzzy = subsequenceScore(label, token);
  // A scattered match needs at least two characters; it ranks below every exact field match.
  return fuzzy !== null && token.length >= 2 ? Math.min(fuzzy, 19) : null;
}

/** Score of an entry for a query (sum over tokens), or null when any token matches nothing. */
export function scorePaletteEntry(entry: PaletteEntry, query: string): number | null {
  const tokens = normalizeForSearch(query).split(/\s+/).filter(Boolean);
  let total = 0;
  for (const token of tokens) {
    const score = tokenScore(entry, token);
    if (score === null) return null;
    total += score;
  }
  return total;
}

export interface PaletteKey {
  readonly key: string;
  readonly altKey: boolean;
  readonly ctrlKey: boolean;
  readonly metaKey: boolean;
}

export type PaletteKeyAction = { readonly type: 'move'; readonly index: number } | { readonly type: 'choose'; readonly index: number } | null;

/**
 * Combobox key handling over `count` results with `current` active (-1 when none): Arrow Up/Down wrap,
 * Home/End jump to the ends (rovingIndex, the sidebar's rule), Enter chooses the active result.
 * Other keys (and modified arrows) are left to the text field.
 */
export function paletteKeyAction(event: PaletteKey, count: number, current: number): PaletteKeyAction {
  if (event.key === 'Enter') return current >= 0 && current < count ? { type: 'choose', index: current } : null;
  if (event.altKey || event.ctrlKey || event.metaKey) return null;
  const index = rovingIndex(count, current, event.key);
  return index === null ? null : { type: 'move', index };
}

/** Matching entries, best first; ties keep the input order (Array.prototype.sort is stable). */
export function rankPaletteEntries<T extends PaletteEntry>(entries: readonly T[], query: string): T[] {
  return entries
    .map(entry => ({ entry, score: scorePaletteEntry(entry, query) }))
    .filter((row): row is { entry: T; score: number } => row.score !== null)
    .sort((a, b) => b.score - a.score)
    .map(row => row.entry);
}
