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
    if (/aria-label(ledby)?=/.test(tag)) continue;
    const before = text.slice(0, start);
    if (before.lastIndexOf("<label") > before.lastIndexOf("</label>")) continue; // wrapped by a label
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

for (const rel of LABELLED) {
  test(`${rel}: every form control has an accessible name`, () => {
    const offenders = unlabelledControls(readFileSync(resolve(process.cwd(), rel), "utf8"));
    assert.deepEqual(offenders, [], `unlabelled controls at lines ${offenders.join(", ")}`);
  });
}
