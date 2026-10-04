import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";

/**
 * Every src/**\/*.tsx file is scanned automatically (so new files are covered) except the explicit EXCLUSIONS below.
 * PINNED_GUARDED is an independent, hand-written list of files that must always be scanned: removing a name from
 * EXCLUSIONS bookkeeping or shrinking the scan cannot silently drop their check.
 */
const EXCLUSIONS: Record<string, string> = {
  // EIS / battery deletion-candidate cluster (.orchestra/DELETION-MANIFEST.md): will be removed, not worth labelling.
  "src/components/AdvancedBatteryPhysicsStudio.tsx": "deletion candidate (EIS/battery cluster)",
  "src/components/BatteryEISDegradationStudio.tsx": "deletion candidate (EIS/battery cluster)",
  "src/components/CircuitLibraryModal.tsx": "deletion candidate (EIS/battery cluster)",
  "src/components/CNLSFittingStudio.tsx": "deletion candidate (EIS/battery cluster)",
  "src/components/EISLabDataUploader.tsx": "deletion candidate (EIS/battery cluster)",
  "src/components/EISUploadInsightsStudio.tsx": "deletion candidate (EIS/battery cluster)",
  "src/components/EquivalentCircuitBuilder.tsx": "deletion candidate (EIS/battery cluster)",
  "src/components/PresetCircuitLibraryPanel.tsx": "deletion candidate (EIS/battery cluster)",
  "src/components/PythonBatteryCorrosionUploadStudio.tsx": "deletion candidate (EIS/battery cluster)",
  "src/components/SavitzkyGolayFilterControls.tsx": "deletion candidate (EIS/battery cluster)",
  "src/components/StochasticUQMMPDSStudio.tsx": "deletion candidate (EIS/battery cluster)",
  "src/components/SyntheticNoiseStressStudio.tsx": "deletion candidate (EIS/battery cluster)",
  "src/components/TransportKineticsLab.tsx": "deletion candidate (EIS/battery cluster)",
  // Thin wrappers: the <input>/<select> is a pass-through element; every call site is wrapped by <label>.
  "src/components/OpticalTomographyLab.tsx": "wrapper-only Input; call sites wrapped by <label>",
  "src/components/PowderDEMCompactionLab.tsx": "wrapper-only Input; call sites wrapped by <label>",
  "src/components/TransientEnthalpy3DGPULab.tsx": "wrapper-only Input/Select; call sites wrapped by <label>",
};
const MAX_EXCLUSIONS = 16; // the list may shrink, never grow silently

// Files labelled in Phase 8 batches 1 and 2; independent of the automatic scan.
const PINNED_GUARDED = [
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
  "src/components/MetallurgicalUnitConverter.tsx",
  "src/components/PocketCalculators.tsx",
  "src/components/InverseAlloyStudio.tsx",
  "src/components/CorrosionEngineeringLab.tsx",
  "src/components/AIOrchestratorPanel.tsx",
  "src/components/AerospaceAuditReportGenerator.tsx",
  "src/components/AlloyBuilder.tsx",
  "src/components/CALPHADMultiComponentStudio.tsx",
  "src/components/CALPHADThermodynamicsLab.tsx",
  "src/components/CorrosionEISKineticsStudio.tsx",
  "src/components/DigitalTwinHub.tsx",
  "src/components/DynamicPourbaixStudio.tsx",
  "src/components/EDSSpectrumLab.tsx",
  "src/components/HeatTreatmentAgingSimulator.tsx",
  "src/components/ICMEMultiScalePipelineStudio.tsx",
  "src/components/IndustrialCertificationLab.tsx",
  "src/components/LpbfBuildJobRail.tsx",
  "src/components/LpbfDefectTwinLab.tsx",
  "src/components/MaterialsDatabaseView.tsx",
  "src/components/MaterialsProjectExplorer.tsx",
  "src/components/MaterialsPropertyHeatmapD3.tsx",
  "src/components/MetallurgicalQuickConversionsGrid.tsx",
  "src/components/MetallurgyCopilot.tsx",
  "src/components/MicroAlloySandbox.tsx",
  "src/components/MicrographLab.tsx",
  "src/components/MurakamiFatigueLab.tsx",
  "src/components/PhaseDiagramViewer.tsx",
  "src/components/PhaseKineticsTTTCCTStudio.tsx",
  "src/components/PythonAnnualCorrosionRateModule.tsx",
  "src/components/SEMAutoAnalyzerStudio.tsx",
  "src/components/StandardQualificationEngine.tsx",
  "src/components/TafelPolarizationLab.tsx",
  "src/components/UQLab.tsx",
  "src/components/WebGLEDSHyperMapCanvas.tsx",
];

const MAX_LABEL_LENGTH = 80;

/**
 * Replace comments and string/template literals by spaces (newlines kept) so JSX tags inside them are ignored.
 * A quote only opens a string in code position (after = ( , : ? [ { | & + ! ; or line start), so apostrophes in
 * JSX text ("Young's") do not swallow code. Quoted strings end at the line end.
 */
export function maskNonCode(src: string): string {
  const out = src.split("");
  const blank = (a: number, b: number) => {
    for (let k = a; k < b; k += 1) if (out[k] !== "\n") out[k] = " ";
  };
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    const n = src[i + 1];
    if (c === "/" && n === "*") {
      const e = src.indexOf("*/", i + 2);
      const stop = e < 0 ? src.length : e + 2;
      blank(i, stop);
      i = stop;
    } else if (c === "/" && n === "/" && src[i - 1] !== ":") {
      let e = src.indexOf("\n", i);
      if (e < 0) e = src.length;
      blank(i, e);
      i = e;
    } else if (c === "`") {
      let j = i + 1;
      while (j < src.length && src[j] !== "`") j += src[j] === "\\" ? 2 : 1;
      blank(i, j + 1);
      i = j + 1;
    } else if (c === '"' || c === "'") {
      let p = i - 1;
      while (p >= 0 && (src[p] === " " || src[p] === "\t")) p -= 1;
      if (p < 0 || "=(,:?[{|&+!;\n".includes(src[p])) {
        let j = i + 1;
        while (j < src.length && src[j] !== c && src[j] !== "\n") j += src[j] === "\\" ? 2 : 1;
        blank(i, j + 1);
        i = j + 1;
      } else i += 1;
    } else i += 1;
  }
  return out.join("");
}

/** End index (of the closing ">") of the tag opening at `start`, ignoring ">" inside {...}. */
function tagEnd(text: string, start: number): number {
  let depth = 0;
  for (let end = start; end < text.length; end += 1) {
    const c = text[end];
    if (c === "{") depth += 1;
    else if (c === "}") depth -= 1;
    else if (c === ">" && depth === 0) return end;
  }
  return text.length - 1;
}

/** aria-label / aria-labelledby with a non-empty, non-undefined value. */
export function hasNonEmptyAriaName(tag: string): boolean {
  for (const m of tag.matchAll(/aria-(?:label|labelledby)=(?:"([^"]*)"|'([^']*)'|\{([^}]*)\})/g)) {
    const raw = (m[1] ?? m[2] ?? m[3] ?? "").trim().replace(/^["'`]|["'`]$/g, "").trim();
    if (raw && !["undefined", "null", "false"].includes(raw)) return true;
  }
  return false;
}

/**
 * True when the text ends inside an unclosed <label>...</label> span (balanced scan). Comments/strings are ignored
 * and a self-closing <label ... /> never opens a span.
 */
export function insideOpenLabel(before: string): boolean {
  const text = maskNonCode(before);
  let depth = 0;
  for (const m of text.matchAll(/<label\b|<\/label>/g)) {
    if (m[0] === "</label>") depth -= 1;
    else {
      const end = tagEnd(text, m.index ?? 0);
      if (text[end - 1] === "/") continue; // <label ... />
      depth += 1;
    }
  }
  return depth > 0;
}

/** Source-level check: returns "line" numbers of form controls with no accessible name. */
export function unlabelledControls(source: string): number[] {
  const text = source.replace(/\r/g, "");
  const code = maskNonCode(text);
  const offenders: number[] = [];
  for (const match of code.matchAll(/<(input|select|textarea)\b/g)) {
    const start = match.index ?? 0;
    const tag = text.slice(start, tagEnd(text, start) + 1);
    if (/type=["']hidden["']/.test(tag)) continue;
    if (hasNonEmptyAriaName(tag)) continue;
    if (insideOpenLabel(text.slice(0, start))) continue; // wrapped by an unclosed <label> span
    const id = tag.match(/\bid=(?:"([^"]+)"|\{([^}]+)\})/);
    const key = id ? id[1] ?? id[2] : undefined;
    if (key && (text.includes(`htmlFor="${key}"`) || text.includes(`htmlFor={${key}}`))) continue;
    offenders.push(text.slice(0, start).split("\n").length);
  }
  return offenders;
}

/** Lines of aria-label values that are too long or merely repeat the placeholder (labels must be short names). */
export function weakLabels(source: string): number[] {
  const text = source.replace(/\r/g, "");
  const code = maskNonCode(text);
  const lines: number[] = [];
  for (const match of code.matchAll(/<(input|select|textarea)\b/g)) {
    const start = match.index ?? 0;
    const tag = text.slice(start, tagEnd(text, start) + 1);
    const m = tag.match(/aria-label=(?:"([^"]*)"|\{`([^`]*)`\})/);
    if (!m) continue;
    const label = (m[1] ?? m[2].replace(/\$\{[^}]*\}/g, "x")).trim();
    const ph = tag.match(/\bplaceholder="([^"]*)"/)?.[1]?.trim();
    const bad = label.length > MAX_LABEL_LENGTH || (ph !== undefined && ph.toLowerCase() === label.toLowerCase());
    if (bad) lines.push(text.slice(0, start).split("\n").length);
  }
  return lines;
}

function listTsx(dir: string): string[] {
  return (readdirSync(resolve(process.cwd(), dir), { recursive: true }) as string[])
    .map((p) => `${dir}/${p.replace(/\\/g, "/")}`)
    .filter((p) => p.endsWith(".tsx"))
    .sort();
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

test("negative fixtures: <label in comments/strings and self-closing labels never cover a control", () => {
  assert.deepEqual(unlabelledControls("{/* <label> */}\n<input />"), [2]);
  assert.deepEqual(unlabelledControls("// <label>\n<input />"), [2]);
  assert.deepEqual(unlabelledControls('const s = "<label>";\n<input />'), [2]);
  assert.deepEqual(unlabelledControls("const s = `<label>`;\n<input />"), [2]);
  assert.deepEqual(unlabelledControls("<label className=\"x\" />\n<input />"), [2]);
  assert.deepEqual(unlabelledControls("<label onClick={() => a > 1} />\n<input />"), [2]);
  // controls inside comments or strings are not real controls
  assert.deepEqual(unlabelledControls("/* <input /> */\n// <select>\nconst s = '<textarea />';"), []);
  // a JSX-text apostrophe must not hide a real offender
  assert.deepEqual(unlabelledControls("<p>Young's modulus</p>\n<input />"), [2]);
  // a real wrapping label still works after a self-closing one
  assert.deepEqual(unlabelledControls("<label />\n<label>A<input /></label>"), []);
});

test("weak labels: too long or equal to the placeholder are rejected", () => {
  assert.deepEqual(weakLabels('<input aria-label="Filter lots" placeholder="Filter lots" />'), [1]);
  assert.deepEqual(weakLabels('<input aria-label="filter LOTS" placeholder="Filter lots" />'), [1]);
  assert.deepEqual(weakLabels(`<input aria-label="${"x".repeat(81)}" />`), [1]);
  assert.deepEqual(weakLabels(`<input aria-label="${"x".repeat(80)}" />`), []);
  assert.deepEqual(weakLabels('<input aria-label="Filter lots" placeholder="Filter Heat/Specimen..." />'), []);
  assert.deepEqual(weakLabels("<input aria-label={`${a} content (${b ? \"wt%\" : \"at%\"})`} />"), []);
});

test("scan covers all src tsx files; exclusions are bounded, existing and justified", () => {
  const all = listTsx("src");
  assert.ok(all.length > 50, "src scan found suspiciously few files");
  assert.ok(Object.keys(EXCLUSIONS).length <= MAX_EXCLUSIONS, "EXCLUSIONS may not grow");
  for (const [rel, reason] of Object.entries(EXCLUSIONS)) {
    assert.ok(reason.trim().length > 0, `${rel} needs a reason`);
    assert.ok(existsSync(resolve(process.cwd(), rel)), `${rel} no longer exists: remove it from EXCLUSIONS`);
  }
  for (const rel of PINNED_GUARDED) {
    assert.ok(all.includes(rel), `${rel} is missing from the src scan`);
    assert.ok(!(rel in EXCLUSIONS), `${rel} is pinned as guarded and cannot be excluded`);
    assert.match(readFileSync(resolve(process.cwd(), rel), "utf8"), /<(input|select|textarea)\b/, `${rel} has no form controls`);
  }
  assert.equal(new Set(PINNED_GUARDED).size, PINNED_GUARDED.length);
});

for (const rel of listTsx("src")) {
  if (rel in EXCLUSIONS) continue;
  test(`${rel}: form controls have accessible names and non-weak labels`, () => {
    const src = readFileSync(resolve(process.cwd(), rel), "utf8");
    const offenders = unlabelledControls(src);
    assert.deepEqual(offenders, [], `unlabelled controls at lines ${offenders.join(", ")}`);
    const weak = weakLabels(src);
    assert.deepEqual(weak, [], `labels too long (>${MAX_LABEL_LENGTH}) or equal to the placeholder at lines ${weak.join(", ")}`);
  });
}
