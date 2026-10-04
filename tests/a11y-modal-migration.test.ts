import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";

// Components whose hand-rolled overlays were migrated to the shared AccessibleModal.
const MIGRATED = [
  "src/App.tsx",
  "src/components/CircuitLibraryModal.tsx",
  "src/components/CNLSFittingStudio.tsx",
  "src/components/EISLabDataUploader.tsx",
  "src/components/EISUploadInsightsStudio.tsx",
  "src/components/EquivalentCircuitBuilder.tsx",
  "src/components/MaterialsDatabaseView.tsx",
  "src/components/SendToModuleModal.tsx",
  "src/components/StandardQualificationEngine.tsx",
  "src/components/TafelPolarizationLab.tsx",
  "src/components/UQLab.tsx",
];

const read = (rel: string) => readFileSync(resolve(process.cwd(), rel), "utf8");

for (const rel of MIGRATED) {
  test(`${rel} uses AccessibleModal and no raw overlay`, () => {
    const text = read(rel);
    assert.match(text, /import \{ AccessibleModal \} from ["'][./]+\/?(components\/)?AccessibleModal["']/);
    assert.match(text, /<AccessibleModal\b/);
    assert.ok(!text.includes("fixed inset-0"), `${rel} reintroduced a raw fixed inset-0 overlay`);
    assert.ok(!/useEscapeToClose\(/.test(text), `${rel} still wires its own Escape handler`);
    assert.ok(!/role=["']dialog["']/.test(text), `${rel} declares a hand-written role="dialog"`);
  });
}

test("every migrated modal has an accessible name", () => {
  for (const rel of MIGRATED) {
    const text = read(rel);
    for (const match of text.matchAll(/<AccessibleModal\b([\s\S]*?)>\r?\n/g)) {
      assert.match(match[1], /\b(label|labelledBy)=/, `${rel}: AccessibleModal without label/labelledBy`);
    }
  }
});
