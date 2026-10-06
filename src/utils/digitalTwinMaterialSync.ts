import type { SampleDigitalTwin } from "../types/digitalTwin";
import type { MaterialMetadata, MaterialSpecimen } from "../store/useMaterialStore";
import { availableProperty } from "./compositionPropertyAvailability";

const PULL_EVIDENCE_NOTE =
  "Composition synchronized from the material store. The store holds no composition-derived mechanical properties, " +
  "so yield, UTS and elongation are unresolved; measurement provenance and qualification remain unresolved.";

/**
 * Digital Twin Hub "Pull from Store": the twin takes the store's composition and identity as they are. An empty store
 * designation (cleared after an edit away from a catalogue alloy) becomes "Unresolved" rather than keeping the twin's
 * previous designation; mechanicals are null unless the record really carries a value.
 */
export function twinFromMaterialSpecimen(prev: SampleDigitalTwin, specimen: MaterialSpecimen): SampleDigitalTwin {
  const designation = (specimen.metadata?.standardDesignation ?? "").trim();
  return {
    ...prev,
    evidence: prev.evidence?.kind === "demo"
      ? prev.evidence
      : { ...prev.evidence, kind: "user-supplied", qualification: "not-assessed", note: PULL_EVIDENCE_NOTE },
    sampleName: specimen.name,
    materialCategory: (specimen.metadata?.category || prev.materialCategory) as SampleDigitalTwin["materialCategory"],
    standardDesignation: designation || "Unresolved",
    chemistry: {
      ...prev.chemistry,
      baseElement: specimen.metadata?.baseMetal || prev.chemistry.baseElement,
      nominalComposition: { ...specimen.composition },
      measuredComposition: undefined,
    },
    mechanical: {
      ...prev.mechanical,
      yieldStrengthMpa: availableProperty(specimen.yieldStrength_25C_MPa),
      ultimateTensileStrengthMpa: availableProperty(specimen.uts_25C_MPa),
      elongationPct: availableProperty(specimen.elongation_pct),
    },
  };
}

/**
 * Designation patch for a twin -> store push. A twin designation is user-supplied (never "catalogue"); an empty or
 * "Unresolved" one clears the store designation.
 */
export function designationPatchFromTwin(
  twin: Pick<SampleDigitalTwin, "standardDesignation">
): Pick<MaterialMetadata, "standardDesignation" | "standardDesignationSource"> {
  const designation = (twin.standardDesignation ?? "").trim();
  return designation && designation !== "Unresolved"
    ? { standardDesignation: designation, standardDesignationSource: "user" }
    : { standardDesignation: "", standardDesignationSource: undefined };
}
