import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";

// Components whose hand-rolled overlays were migrated to the shared AccessibleModal.
const MIGRATED = [
  "src/App.tsx",
  "src/components/MaterialsDatabaseView.tsx",
  "src/components/SendToModuleModal.tsx",
  "src/components/StandardQualificationEngine.tsx",
  "src/components/TafelPolarizationLab.tsx",
  "src/components/UQLab.tsx",
];

const read = (rel: string) => readFileSync(resolve(process.cwd(), rel), "utf8").replace(/\r/g, "");

/** Returns the full opening tag text of every <AccessibleModal ...>, honouring braces so `=>` is not a tag end. */
export function modalOpeningTags(source: string): string[] {
  const tags: string[] = [];
  for (const match of source.matchAll(/<AccessibleModal\b/g)) {
    const start = match.index ?? 0;
    let depth = 0;
    let quote: string | null = null;
    let end = start;
    for (; end < source.length; end += 1) {
      const c = source[end];
      if (quote) {
        if (c === quote) quote = null;
        continue;
      }
      if (c === '"') quote = c;
      else if (c === "{") depth += 1;
      else if (c === "}") depth -= 1;
      else if (c === ">" && depth === 0) break;
    }
    tags.push(source.slice(start, end + 1));
  }
  return tags;
}

/** Problems with one opening tag: missing/empty name, dangling labelledBy id, no-op onClose. */
export function modalTagProblems(tag: string, source: string): string[] {
  const problems: string[] = [];
  const label = tag.match(/\blabel=(?:"([^"]*)"|\{\s*"([^"]*)"\s*\})/);
  const labelledBy = tag.match(/\blabelledBy="([^"]*)"/);
  const labelText = label ? (label[1] ?? label[2] ?? "").trim() : "";
  if (labelledBy) {
    const id = labelledBy[1].trim();
    if (!id || !new RegExp(`\\bid=["']${id}["']`).test(source)) problems.push(`labelledBy "${id}" has no matching id in the file`);
  } else if (!labelText) {
    problems.push("no non-empty label or labelledBy");
  }
  if (/\bonClose=\{\s*\(\s*\)\s*=>\s*(\{\s*\}|undefined|null|void 0)\s*\}/.test(tag)) problems.push("onClose is a no-op");
  if (!/\bonClose=/.test(tag)) problems.push("no onClose");
  return problems;
}

test("modalOpeningTags / modalTagProblems negative fixtures", () => {
  const good = '<AccessibleModal open onClose={() => setX(false)} label="Hi" panelClassName="a">';
  assert.deepEqual(modalOpeningTags(good + "x</AccessibleModal>"), [good]);
  assert.deepEqual(modalTagProblems(good, ""), []);
  assert.deepEqual(modalTagProblems('<AccessibleModal open onClose={() => setX(false)} label="">', ""), ["no non-empty label or labelledBy"]);
  assert.deepEqual(modalTagProblems("<AccessibleModal open onClose={() => setX(false)}>", ""), ["no non-empty label or labelledBy"]);
  assert.match(modalTagProblems('<AccessibleModal open onClose={() => setX(false)} labelledBy="gone">', '<h2 id="other">')[0], /no matching id/);
  assert.deepEqual(modalTagProblems('<AccessibleModal open onClose={() => setX(false)} labelledBy="t">', '<h2 id="t">'), []);
  assert.deepEqual(modalTagProblems('<AccessibleModal open onClose={() => {}} label="a">', ""), ["onClose is a no-op"]);
  assert.deepEqual(modalTagProblems('<AccessibleModal open onClose={() => undefined} label="a">', ""), ["onClose is a no-op"]);
  assert.deepEqual(modalTagProblems('<AccessibleModal open label="a">', ""), ["no onClose"]);
  // multi-line tag with an arrow function containing ">" characters
  const multi = '<AccessibleModal\n  open\n  onClose={() => { if (a > b) c(); }}\n  label="L"\n>';
  assert.equal(modalOpeningTags(multi).length, 1);
  assert.equal(modalOpeningTags(multi)[0], multi);
});

for (const rel of MIGRATED) {
  test(`${rel} uses AccessibleModal and no raw overlay`, () => {
    const text = read(rel);
    assert.match(text, /import \{ AccessibleModal \} from ["'][./]+\/?(components\/)?AccessibleModal["']/);
    assert.ok(!text.includes("fixed inset-0"), `${rel} reintroduced a raw fixed inset-0 overlay`);
    assert.ok(!/useEscapeToClose\(/.test(text), `${rel} still wires its own Escape handler`);
    assert.ok(!/role=["']dialog["']/.test(text), `${rel} declares a hand-written role="dialog"`);
    const tags = modalOpeningTags(text);
    assert.ok(tags.length >= 1, `${rel} has no <AccessibleModal>`);
    for (const tag of tags) assert.deepEqual(modalTagProblems(tag, text), [], `${rel}: ${tag.slice(0, 80)}`);
  });
}

test("App engine status modal keeps backdrop close, its label id and no ad-hoc Escape listener", () => {
  const text = read("src/App.tsx");
  const tag = modalOpeningTags(text)[0];
  assert.match(tag, /\bcloseOnBackdrop\b/);
  assert.match(tag, /labelledBy="engine-title"/);
  assert.ok(!/addEventListener\(\s*["']keydown["']/.test(text), "App must not register its own keydown/Escape listener");
  assert.ok(!/event\.key === ['"]Escape['"]/.test(text), "App must not handle Escape itself");
  assert.ok(!/<button[^>]*\bautoFocus\b/.test(text), "autoFocus must not return (focus is managed by AccessibleModal)");
});
