import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { test } from "node:test";

const SRC_ROOT = resolve(process.cwd(), "src");

// Overlays without role="dialog" on the overlay or its first child are listed here as "path:line" with a reason.
// Currently empty: every fixed inset-0 overlay (including the App.tsx engine status panel) declares role="dialog".
const OVERLAY_ALLOW_LIST: string[] = [];

function listTsx(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) out.push(...listTsx(full));
    else if (name.endsWith(".tsx")) out.push(full);
  }
  return out;
}

const files = listTsx(SRC_ROOT).map((full) => ({
  rel: relative(process.cwd(), full).replace(/\\/g, "/"),
  text: readFileSync(full, "utf8"),
}));

function lineOf(text: string, index: number): number {
  return text.slice(0, index).split("\n").length;
}

test("every <img> element has an alt attribute", () => {
  const offenders: string[] = [];
  for (const { rel, text } of files) {
    for (const match of text.matchAll(/<img\b/g)) {
      const start = match.index ?? 0;
      // Scan the tag up to its closing "/>" or ">" that follows the attributes.
      const tail = text.slice(start, start + 2000);
      const end = tail.search(/\/>|[^=]>/);
      const tag = end === -1 ? tail : tail.slice(0, end + 2);
      if (!/\balt\s*=/.test(tag) && !/\{\s*\.\.\./.test(tag)) {
        offenders.push(`${rel}:${lineOf(text, start)}`);
      }
    }
  }
  assert.deepEqual(offenders, [], `<img> without alt: ${offenders.join(", ")}`);
});

test("fixed inset-0 overlays declare role=\"dialog\"", () => {
  const offenders: string[] = [];
  for (const { rel, text } of files) {
    for (const match of text.matchAll(/fixed inset-0/g)) {
      const start = match.index ?? 0;
      const id = `${rel}:${lineOf(text, start)}`;
      if (OVERLAY_ALLOW_LIST.includes(id)) continue;
      // The dialog container is either the overlay itself or its first child.
      const window = text.slice(start, start + 700);
      if (!/role=\{?["']dialog["']/.test(window)) offenders.push(id);
    }
  }
  assert.deepEqual(offenders, [], `Overlays without role="dialog": ${offenders.join(", ")}`);
});

test("Escape handling for overlays goes through the shared stack, not ad-hoc window listeners", () => {
  const hook = readFileSync(resolve(SRC_ROOT, "components/AccessibleModal.tsx"), "utf8");
  assert.match(hook, /escapeStack/);
  const offenders = files
    .filter(({ rel }) => rel.startsWith("src/components/") && rel !== "src/components/AccessibleModal.tsx")
    .filter(({ text }) => text.includes("fixed inset-0")) // popovers such as StandardInfoIcon are not overlays
    .filter(({ text }) => /addEventListener\(\s*["']keydown["']/.test(text) && /Escape/.test(text))
    .map(({ rel }) => rel);
  assert.deepEqual(offenders, [], `Use useEscapeToClose instead: ${offenders.join(", ")}`);
});
