/**
 * Pure filtering, ranking and choice logic for the command palette (Phase 9 shell, DESIGN-9 section 3).
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

/** Longest query the palette field accepts (the input's maxLength). */
export const PALETTE_QUERY_MAX_LENGTH = 120;

/** Lower case without combining diacritics, dotless i folded to i: "resume" finds "Résumé", "celik" a Turkish "Çelik". */
export function normalizeForSearch(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/\u0131/g, 'i');
}

const isWordStart = (text: string, index: number) => index === 0 || !/[a-z0-9]/.test(text[index - 1]);

/** Index of the first occurrence of `token` in `text` that starts a word, or -1. */
function wordStartIndex(text: string, token: string): number {
  for (let at = text.indexOf(token); at !== -1; at = text.indexOf(token, at + 1)) {
    if (isWordStart(text, at)) return at;
  }
  return -1;
}

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

/** Highest score a scattered (subsequence) label match can reach: below every exact field match. */
export const FUZZY_SCORE_CAP = 19;

interface NormalizedEntry { readonly label: string; readonly id: string; readonly workspace: string; readonly scope: string; readonly description: string }
// Entries are static (the registry), so each is normalized once, not on every keystroke.
const normalized = new WeakMap<PaletteEntry, NormalizedEntry>();
function normalizedEntry(entry: PaletteEntry): NormalizedEntry {
  let value = normalized.get(entry);
  if (!value) {
    value = {
      label: normalizeForSearch(entry.label), id: normalizeForSearch(entry.id), workspace: normalizeForSearch(entry.workspaceLabel),
      scope: normalizeForSearch(entry.scope), description: normalizeForSearch(entry.description),
    };
    normalized.set(entry, value);
  }
  return value;
}

/**
 * Best score of one token against one entry, or null when no field matches.
 * A one-character token matches only the start of a word in the label: id, workspace, maturity and
 * description substrings (and scattered letters) need two or more characters, because one common letter
 * is contained in every workspace or maturity name and would list every module.
 */
function tokenScore(entry: PaletteEntry, token: string): number | null {
  const fields = normalizedEntry(entry);
  if (fields.label.startsWith(token)) return 120;
  if (wordStartIndex(fields.label, token) > 0) return 100;
  if (token.length < 2) return null;
  if (fields.label.includes(token)) return 80;
  if (fields.id.includes(token)) return 60;
  if (fields.workspace.includes(token) || fields.scope.includes(token)) return 40;
  if (fields.description.includes(token)) return 20;
  const fuzzy = subsequenceScore(fields.label, token);
  return fuzzy === null ? null : Math.min(fuzzy, FUZZY_SCORE_CAP);
}

/** Score of an entry for a query (sum over tokens), or null when any token matches nothing. */
export function scorePaletteEntry(entry: PaletteEntry, query: string): number | null {
  // Whitespace, punctuation and symbols separate tokens: "EBSD/CT", "thermal-map" and "&" carry no letter to match.
  const tokens = normalizeForSearch(query).split(/[\s\p{P}\p{S}]+/u).filter(Boolean);
  let total = 0;
  for (const token of tokens) {
    const score = tokenScore(entry, token);
    if (score === null) return null;
    total += score;
  }
  return total;
}

/** Matching entries, best first; ties keep the input order (Array.prototype.sort is stable). */
export function rankPaletteEntries<T extends PaletteEntry>(entries: readonly T[], query: string): T[] {
  return entries
    .map(entry => ({ entry, score: scorePaletteEntry(entry, query) }))
    .filter((row): row is { entry: T; score: number } => row.score !== null)
    .sort((a, b) => b.score - a.score)
    .map(row => row.entry);
}

export interface PaletteKey {
  readonly key: string;
  readonly altKey: boolean;
  readonly ctrlKey: boolean;
  readonly metaKey: boolean;
  /** KeyboardEvent.isComposing (IME composition in progress). */
  readonly isComposing?: boolean;
  /** 229 is reported for keys an IME is processing (older browsers do not set isComposing). */
  readonly keyCode?: number;
}

/** True while an IME is composing: the key belongs to the composition, not to the palette. */
export function isComposingKey(event: Pick<PaletteKey, 'isComposing' | 'keyCode'>): boolean {
  return event.isComposing === true || event.keyCode === 229;
}

export type PaletteKeyAction = { readonly type: 'move'; readonly index: number } | { readonly type: 'choose'; readonly index: number } | null;

/**
 * Combobox key handling over `count` results with `current` active (-1 when none): Arrow Up/Down wrap,
 * Home/End jump to the ends (rovingIndex, the sidebar's rule), Enter chooses the active result.
 * Keys of an IME composition, other keys and modified arrows are left to the text field.
 */
export function paletteKeyAction(event: PaletteKey, count: number, current: number): PaletteKeyAction {
  if (isComposingKey(event)) return null;
  if (event.key === 'Enter') return current >= 0 && current < count ? { type: 'choose', index: current } : null;
  if (event.altKey || event.ctrlKey || event.metaKey) return null;
  const index = rovingIndex(count, current, event.key);
  return index === null ? null : { type: 'move', index };
}

/** The module a choice opens: the result at `index` (the active option on Enter, the clicked option on click), or null. */
export function paletteChoice(results: readonly { readonly id: string }[], index: number): string | null {
  return Number.isInteger(index) && index >= 0 && index < results.length ? results[index].id : null;
}

export interface PaletteEffects {
  /** The shell's navigate(): the same function the sidebar calls. */
  readonly navigate: (id: string) => void;
  readonly close: () => void;
  readonly setActive: (index: number) => void;
}

/** Opens the chosen module and closes the palette; nothing happens (returns null) when there is no such result. */
export function commitPaletteChoice(results: readonly { readonly id: string }[], index: number, effects: Pick<PaletteEffects, 'navigate' | 'close'>): string | null {
  const id = paletteChoice(results, index);
  if (id === null) return null;
  effects.navigate(id);
  effects.close();
  return id;
}

/** Keydown on the palette field. Returns true when the event was handled (the caller prevents the default). */
export function handlePaletteInputKey(event: PaletteKey, results: readonly { readonly id: string }[], current: number, effects: PaletteEffects): boolean {
  const action = paletteKeyAction(event, results.length, current);
  if (!action) return false;
  if (action.type === 'choose') commitPaletteChoice(results, action.index, effects);
  else effects.setActive(action.index);
  return true;
}
