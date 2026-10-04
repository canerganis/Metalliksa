import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { MODULES, WORKSPACES } from '../src/data/workspaces';
import { LISTED_CONTRACTS } from '../src/modules/registry';
import {
  FUZZY_SCORE_CAP, normalizeForSearch, paletteKeyAction, rankPaletteEntries, scorePaletteEntry, subsequenceScore, type PaletteEntry,
} from '../src/utils/commandPalette';
import { isPaletteShortcut, paletteShortcutLabel } from '../src/hooks/useCommandPaletteShortcut';

// Phase 9 command palette: pure ranking over the registry-derived navigation list (MODULES).
const ENTRIES = MODULES.map(module => ({
  ...module,
  workspaceLabel: WORKSPACES.find(workspace => workspace.id === module.workspace)!.label,
}));
const ids = (query: string) => rankPaletteEntries(ENTRIES, query).map(entry => entry.id);
const entry = (label: string, extra: Partial<PaletteEntry> = {}): PaletteEntry =>
  ({ id: label.toLowerCase().replace(/\W+/g, '-'), label, description: '', scope: 'Research', workspaceLabel: 'W', ...extra });

test('the palette source list is the registry: every listed contract, in navigation order', () => {
  assert.deepEqual(ENTRIES.map(e => e.id), LISTED_CONTRACTS.map(contract => contract.id));
  assert.deepEqual(ids(''), MODULES.map(module => module.id), 'empty query = sidebar order, nothing dropped');
  assert.deepEqual(ids('   '), MODULES.map(module => module.id));
});

test('normalization folds case and diacritics', () => {
  assert.equal(normalizeForSearch('Alaşım İÇ Çelik'), 'alasim ic celik');
  assert.equal(normalizeForSearch('Résumé'), 'resume');
});

test('subsequence score: null when a character is missing, higher for consecutive and word-start runs', () => {
  assert.equal(subsequenceScore('keyhole ray tracing', 'kz'), null);
  assert.equal(subsequenceScore('abc', ''), 0);
  const tight = subsequenceScore('keyhole ray tracing', 'key')!;
  const loose = subsequenceScore('keyhole ray tracing', 'kye')!;
  assert.ok(tight > loose, `${tight} > ${loose}`);
  assert.ok(subsequenceScore('ray tracing', 'rt')! > subsequenceScore('rapid xt', 'rt')!, 'word starts outrank inner letters');
});

test('label prefix outranks word start, inner substring, id, workspace and description matches', () => {
  const list = [
    entry('Gamma description', { description: 'mentions keyhole here' }),
    entry('Alpha', { id: 'keyhole-id' }),
    entry('Inner xkeyhole'),
    entry('Ray keyhole'),
    entry('Keyhole first'),
    entry('Beta', { workspaceLabel: 'Keyhole workspace' }),
  ];
  assert.deepEqual(rankPaletteEntries(list, 'keyhole').map(e => e.label),
    ['Keyhole first', 'Ray keyhole', 'Inner xkeyhole', 'Alpha', 'Beta', 'Gamma description']);
});

test('every token must match (AND); scattered letters match the label only, ranked below exact matches', () => {
  assert.equal(ids('thermal map')[0], 'toolpath-thermal-map');
  assert.ok(ids('thermal map').every(id => scorePaletteEntry(ENTRIES.find(e => e.id === id)!, 'map') !== null));
  assert.equal(ids('kyhl')[0], 'keyhole-raytracing', 'fuzzy subsequence on the label');
  assert.equal(scorePaletteEntry(entry('Keyhole'), 'kyhl')! < scorePaletteEntry(entry('Other', { description: 'kyhl' }), 'kyhl')!, true);
  assert.deepEqual(ids('zzqqxx'), []);
  assert.deepEqual(ids('keyhole zzqqxx'), [], 'one unmatched token removes the entry');
});

test('real registry queries: label, id and workspace hits', () => {
  assert.equal(ids('keyhole')[0], 'keyhole-raytracing');
  assert.equal(ids('fno')[0], 'modulus-fno-lab');
  assert.equal(ids('calphad')[0], 'phase-diagram');
  const evidence = ids('evidence & qualification');
  const inEvidence = MODULES.filter(module => module.workspace === 'evidence').map(module => module.id);
  for (const id of inEvidence) assert.ok(evidence.includes(id), `${id} found by its workspace name`);
  assert.ok(ids('preview').length >= MODULES.filter(module => module.scope === 'Preview').length, 'scope is searchable');
});

test('a single letter matches only word starts in labels (not id, workspace, maturity, description or inner letters)', () => {
  const list = [
    entry('Alpha', { description: 'q in description', id: 'q-id', workspaceLabel: 'Q workspace', scope: 'Q' }),
    entry('Quench'), entry('Big Quartz'), entry('Aqua'),
  ];
  assert.deepEqual(rankPaletteEntries(list, 'q').map(e => e.label), ['Quench', 'Big Quartz']);
  assert.equal(rankPaletteEntries([entry('Keyhole')], 'y').length, 0, 'an inner letter is not enough');
  assert.equal(rankPaletteEntries([entry('Kxxxxe')], 'ke').length, 1, 'two-letter subsequence counts');
});

test('real registry: one letter never lists every module; each hit has a label word starting with it', () => {
  for (const letter of 'abcdefghijklmnopqrstuvwxyz') {
    const hits = ids(letter);
    assert.ok(hits.length < MODULES.length, `"${letter}" lists ${hits.length} of ${MODULES.length}`);
    for (const id of hits) {
      const label = normalizeForSearch(ENTRIES.find(e => e.id === id)!.label);
      assert.ok(label.split(/[^a-z0-9]+/).some(word => word.startsWith(letter)), `"${letter}" -> ${id}`);
    }
  }
  // The review's measured cases: e, r and i used to match all 37 through workspace and maturity names.
  for (const letter of ['e', 'r', 'i', 'İ', 'ı']) assert.ok(ids(letter).length < MODULES.length, letter);
  assert.deepEqual(ids('k'), ['keyhole-raytracing', 'toolpath-studio'], 'Keyhole Ray Tracing (prefix) before Toolpath & Kinematics (word start)');
  assert.ok(ids('re').length > ids('r').length, 'two characters reach id, workspace, maturity and description');
});

test('a later word-start occurrence counts as a word start', () => {
  assert.equal(scorePaletteEntry(entry('Axkey key'), 'key'), 100);
  assert.equal(scorePaletteEntry(entry('Axkey'), 'key'), 80);
});

test('scattered matches are capped below every exact field match', () => {
  const long = entry('Abcdefghijklmnopqrstuvwxyz');
  const raw = subsequenceScore(normalizeForSearch(long.label), 'acdefghij')!;
  assert.ok(raw > FUZZY_SCORE_CAP, `uncapped ${raw}`);
  assert.equal(scorePaletteEntry(long, 'acdefghij'), FUZZY_SCORE_CAP);
  assert.ok(FUZZY_SCORE_CAP < 20, 'below a description match (20)');
});

test('punctuation and symbols separate tokens; a query of only symbols lists everything', () => {
  assert.deepEqual(ids('ebsd/ct'), ids('ebsd ct'));
  assert.equal(ids('thermal-map')[0], 'toolpath-thermal-map');
  assert.deepEqual(ids('&'), MODULES.map(module => module.id));
  assert.deepEqual(ids('кейхол'), [], 'letters outside the labels match nothing');
});

test('normalization uses visible escapes and folds the dotted and dotless i', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/utils/commandPalette.ts'), 'utf8');
  assert.match(source, /\/\[\\u0300-\\u036f\]\/g/);
  assert.match(source, /\/\\u0131\/g/);
  assert.doesNotMatch(source, /[\u0300-\u036f\u0131]/, 'no invisible combining or dotless characters in the source');
  assert.equal(normalizeForSearch('İı'), 'ii');
});

test('ties keep the input (registry) order', () => {
  const list = [entry('Lab one'), entry('Lab two'), entry('Lab three')];
  assert.deepEqual(rankPaletteEntries(list, 'lab').map(e => e.label), ['Lab one', 'Lab two', 'Lab three']);
});

test('keys: arrows wrap, Home/End jump, Enter chooses the active result, other keys stay with the field', () => {
  const plain = (key: string) => ({ key, altKey: false, ctrlKey: false, metaKey: false });
  assert.deepEqual(paletteKeyAction(plain('ArrowDown'), 3, 0), { type: 'move', index: 1 });
  assert.deepEqual(paletteKeyAction(plain('ArrowDown'), 3, 2), { type: 'move', index: 0 });
  assert.deepEqual(paletteKeyAction(plain('ArrowUp'), 3, 0), { type: 'move', index: 2 });
  assert.deepEqual(paletteKeyAction(plain('Home'), 3, 2), { type: 'move', index: 0 });
  assert.deepEqual(paletteKeyAction(plain('End'), 3, 0), { type: 'move', index: 2 });
  assert.deepEqual(paletteKeyAction(plain('Enter'), 3, 1), { type: 'choose', index: 1 });
  assert.equal(paletteKeyAction(plain('Enter'), 0, -1), null, 'Enter with no results does nothing');
  assert.equal(paletteKeyAction(plain('ArrowDown'), 0, -1), null);
  assert.equal(paletteKeyAction(plain('a'), 3, 0), null);
  assert.equal(paletteKeyAction(plain('Escape'), 3, 0), null, 'Escape belongs to AccessibleModal');
  assert.equal(paletteKeyAction({ ...plain('ArrowDown'), altKey: true }, 3, 0), null);
});

test('shortcut: Ctrl+K or Cmd+K only; the hint follows the platform', () => {
  const key = (k: string, mods: Partial<{ ctrlKey: boolean; metaKey: boolean; altKey: boolean; shiftKey: boolean }> = {}) =>
    ({ key: k, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...mods });
  assert.ok(isPaletteShortcut(key('k', { ctrlKey: true })));
  assert.ok(isPaletteShortcut(key('K', { metaKey: true })), 'Caps Lock');
  assert.ok(!isPaletteShortcut(key('k')));
  assert.ok(!isPaletteShortcut(key('k', { ctrlKey: true, shiftKey: true })));
  assert.ok(!isPaletteShortcut(key('k', { ctrlKey: true, altKey: true })));
  assert.ok(!isPaletteShortcut(key('j', { ctrlKey: true })));
  assert.equal(paletteShortcutLabel('MacIntel'), '⌘K');
  assert.equal(paletteShortcutLabel('iPhone'), '⌘K');
  assert.equal(paletteShortcutLabel('Win32'), 'Ctrl K');
  assert.equal(paletteShortcutLabel(''), 'Ctrl K');
});
