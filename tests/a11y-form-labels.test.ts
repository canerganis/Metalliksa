import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";

// LPBF / simulation workspace components whose form controls were labelled in Phase 8 batch 1.
const LABELLED = [
  "src/components/3d-distortion-lab/LpbfEngineeringSimulation.tsx",
  "src/components/3d-distortion-lab/LPBFGroundTruthDataLab.tsx",
  "src/components/3d-distortion-lab/BasicSTLSlicerLab.tsx",
  "src/components/3d-distortion-lab/MarangoniPoreInstabilityLab.tsx",
  "src/components/3d-distortion-lab/EmbeddedPythonLPBFSimulator.tsx",
  "src/components/3d-distortion-lab/IndustrialLPBFDecisionLab.tsx",
  "src/components/3d-distortion-lab/MeltPool3DCrossSectionLab.tsx",
  "src/components/LpbfBayesianOptimizerLab.tsx",
  "src/components/MultiLaserPlumeLab.tsx",
  "src/components/MultiTrackThermalLab.tsx",
  "src/components/LaserMeltPoolThermalMap.tsx",
  "src/components/LPBFAdditivePhysicsSuite.tsx",
  "src/components/ToolpathThermalMapLab.tsx",
  "src/components/LpbfAdaptiveMitigationLab.tsx",
  "src/components/LpbfToolpathStudioLab.tsx",
];

/** aria-label / aria-labelledby with a non-empty, non-undefined value. */
export function hasNonEmptyAriaName(tag: string): boolean {
  for (const m of tag.matchAll(/aria-(?:label|labelledby)=(?:"([^"]*)"|'([^']*)'|\{([^}]*)\})/g)) {
    const raw = (m[1] ?? m[2] ?? m[3] ?? "").trim().replace(/^["'`]|["'`]$/g, "").trim();
    if (raw && !["undefined", "null", "false"].includes(raw)) return true;
  }
  return false;
}

/** True when the text ends inside an unclosed <label>...</label> span (balanced scan, not "last <label"). */
export function insideOpenLabel(before: string): boolean {
  let depth = 0;
  for (const m of before.matchAll(/<label\b|<\/label>/g)) depth += m[0] === "</label>" ? -1 : 1;
  return depth > 0;
}

/** Source-level check: returns "line" numbers of form controls with no accessible name. */
export function unlabelledControls(source: string): number[] {
  const text = source.replace(/\r/g, "");
  const offenders: number[] = [];
  for (const match of text.matchAll(/<(input|select|textarea)\b/g)) {
    const start = match.index ?? 0;
    let depth = 0;
    let end = start;
    for (; end < text.length; end += 1) {
      const c = text[end];
      if (c === "{") depth += 1;
      else if (c === "}") depth -= 1;
      else if (c === ">" && depth === 0) break;
    }
    const tag = text.slice(start, end + 1);
    if (/type=["']hidden["']/.test(tag)) continue;
    if (hasNonEmptyAriaName(tag)) continue;
    const before = text.slice(0, start);
    if (insideOpenLabel(before)) continue; // wrapped by an unclosed <label> span
    const id = tag.match(/\bid=(?:"([^"]+)"|\{([^}]+)\})/);
    const key = id ? id[1] ?? id[2] : undefined;
    if (key && (text.includes(`htmlFor="${key}"`) || text.includes(`htmlFor={${key}}`))) continue;
    offenders.push(before.split("\n").length);
  }
  return offenders;
}

test("detector flags a bare control and accepts the three labelling forms", () => {
  assert.deepEqual(unlabelledControls("<div>\n<input type=\"range\" />\n</div>"), [2]);
  assert.deepEqual(unlabelledControls('<input aria-label="x" />'), []);
  assert.deepEqual(unlabelledControls("<label>Name<input /></label>"), []);
  assert.deepEqual(unlabelledControls('<label htmlFor="a">A</label><input id="a" />'), []);
  assert.deepEqual(unlabelledControls("<label>A</label><input />"), [1]);
});

test("negative fixtures: empty or undefined aria names and stale label spans do not count", () => {
  assert.deepEqual(unlabelledControls('<input aria-label="" />'), [1]);
  assert.deepEqual(unlabelledControls('<input aria-label="  " />'), [1]);
  assert.deepEqual(unlabelledControls("<input aria-label={undefined} />"), [1]);
  assert.deepEqual(unlabelledControls('<input aria-label={""} />'), [1]);
  assert.deepEqual(unlabelledControls('<input aria-labelledby="" />'), [1]);
  assert.deepEqual(unlabelledControls("<input aria-label={name} />"), []);
  // an earlier, already closed label must not cover a later bare control
  assert.deepEqual(unlabelledControls("<label>A</label>\n<div>\n<input />\n</div>"), [3]);
  assert.deepEqual(unlabelledControls("<label>A<span></span></label><label>B</label><input />"), [1]);
  // controls inside one open label span are covered; after it closes they are not
  assert.deepEqual(unlabelledControls("<label>A<input /><input /></label><input />"), [1]);
  assert.equal(insideOpenLabel("<label>x"), true);
  assert.equal(insideOpenLabel("<label>x</label>"), false);
});

for (const rel of LABELLED) {
  test(`${rel}: every form control has an accessible name`, () => {
    const offenders = unlabelledControls(readFileSync(resolve(process.cwd(), rel), "utf8"));
    assert.deepEqual(offenders, [], `unlabelled controls at lines ${offenders.join(", ")}`);
  });
}
