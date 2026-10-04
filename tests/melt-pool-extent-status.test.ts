import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  isComputedMeltPoolExtent,
  literatureErrorUnavailableText,
  meltPoolExtentInfo,
} from "../src/utils/meltPoolExtentStatus";
import { toActionableReason } from "../src/utils/lpbfActionableReasons";

const read = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("only extentStatus 'computed' is a computed isotherm; a missing status never is", () => {
  assert.equal(isComputedMeltPoolExtent({ extentStatus: "computed", extentNote: null }), true);
  for (const status of ["heuristic-width-fallback", "width-floor-applied", "search-box-limited", "something-new"]) {
    assert.equal(isComputedMeltPoolExtent({ extentStatus: status }), false, status);
  }
  assert.equal(isComputedMeltPoolExtent({}), false);
  assert.equal(isComputedMeltPoolExtent(null), false);
  assert.equal(meltPoolExtentInfo({}).status, "not-reported");
});

test("status to label/description/note mapping", () => {
  const fb = meltPoolExtentInfo({ extentStatus: "heuristic-width-fallback", extentNote: "no resolvable melt" });
  assert.equal(fb.status, "heuristic-width-fallback");
  assert.equal(fb.note, "no resolvable melt");
  assert.match(fb.description, /heuristic/);
  assert.match(meltPoolExtentInfo({ extentStatus: "width-floor-applied" }).description, /floor/);
  assert.match(meltPoolExtentInfo({ extentStatus: "search-box-limited" }).description, /lower bound/);
  assert.equal(meltPoolExtentInfo({ extentStatus: "computed", extentNote: "" }).note, null);
});

test("literature % error is replaced by 'not computed — <status>' unless computed", () => {
  assert.equal(literatureErrorUnavailableText({ extentStatus: "computed" }), null);
  assert.equal(
    literatureErrorUnavailableText({ extentStatus: "heuristic-width-fallback" }),
    "not computed — heuristic-width-fallback",
  );
  assert.equal(literatureErrorUnavailableText({ extentStatus: "width-floor-applied" }), "not computed — width-floor-applied");
  assert.equal(literatureErrorUnavailableText({}), "not computed — not-reported");
});

test("the three melt-pool views render the shared notice; the literature % error guards on the status util", () => {
  for (const view of [
    "src/components/3d-distortion-lab/MeltPool3DCrossSectionLab.tsx",
    "src/components/LaserMeltPoolThermalMap.tsx",
    "src/components/3d-distortion-lab/IndustrialLPBFDecisionLab.tsx",
  ]) {
    const src = read(view);
    assert.match(src, /import \{ MeltPoolExtentNotice \} from/, view);
    assert.match(src, /<MeltPoolExtentNotice geometry=\{[^}]*meltPoolGeometry\}/, view);
  }
  assert.match(read("src/components/MeltPoolExtentNotice.tsx"), /meltPoolExtentInfo/);
  const lab = read("src/components/3d-distortion-lab/MeltPool3DCrossSectionLab.tsx");
  assert.match(lab, /literatureErrorUnavailableText\(pyResult\.meltPoolGeometry\)/);
  assert.match(lab, /const wErr = canScore && errorExcluded === null/);
  assert.match(lab, /const dErr = canScore && errorExcluded === null/);
  assert.match(lab, /\{canScore && errorExcluded === null && \(/);
  assert.match(lab, /\{canScore && errorExcluded !== null && \(/);
  const decision = read("src/components/3d-distortion-lab/IndustrialLPBFDecisionLab.tsx");
  assert.match(decision, /isComputedMeltPoolExtent\(thermal\.meltPoolGeometry\)/);
  assert.match(decision, /v === "inconclusive"/);
  assert.match(decision, /not computed — \{c\.extentStatus/);
});

test("types declare extentStatus/extentNote in both meltPoolGeometry blocks", () => {
  const svc = read("src/services/pythonComputationService.ts");
  assert.match(svc, /extentStatus: MeltPoolExtentStatus;\r?\n\s*extentNote: string \| null;/);
  assert.match(svc, /extentStatus\?: MeltPoolExtentStatus;\r?\n\s*extentNote\?: string \| null;/);
  assert.match(svc, /verdict: "printable" \| "risky" \| "do-not-print" \| "inconclusive"/);
});

test("unresolved-geometry reasons are not given LoF/balling advice", () => {
  const line =
    "Lack-of-fusion (Tang h/W, t/D, W/h, D/t) and balling (L/W) gates unavailable: melt-pool geometry not resolved (heuristic-width-fallback): note. No print / do-not-print verdict is issued from heuristic geometry.";
  assert.equal(toActionableReason(line), line);
  // A real LoF reason still gets its action.
  assert.match(toActionableReason("Lack of fusion (Tang): (h/W)²+(t/D)² = 1.2 (need ≤1.0); W/h = 0.9, D/t = 1.0."), /Action:/);
});
