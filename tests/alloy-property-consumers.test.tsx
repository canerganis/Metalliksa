import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { CALPHADMultiComponentStudio } from "../src/components/CALPHADMultiComponentStudio";
import { SendToModuleModal, celsiusOrUnavailable, mpaOrUnavailable } from "../src/components/SendToModuleModal";
import { deriveSpecimenProperties, SPECIMEN_PRESETS, useMaterialSpecimenStore } from "../src/store/useMaterialSpecimenStore";
import { deriveProperties, MATERIAL_PRESETS, useMaterialStore, type MaterialSpecimen } from "../src/store/useMaterialStore";
import { specimenStrengthsToLoad } from "../src/utils/compositionPropertyAvailability";
import { designationPatchFromTwin, twinFromMaterialSpecimen } from "../src/utils/digitalTwinMaterialSync";
import { DEFAULT_DIGITAL_TWINS } from "../src/data/digitalTwinStore";
import { MATERIALS_DATABASE } from "../src/data/materialsDatabase";
import {
  createPipelinePayloadFromMaterialSpec,
  getActivePipelineMaterial,
  type PipelineMaterialPayload,
} from "../src/utils/materialDataPipeline";

const textOf = (markup: string) =>
  markup.replace(/<[^>]+>/g, " ").replace(/&#x27;/g, "'").replace(/&amp;/g, "&").replace(/\s+/g, " ");

test("CALPHAD studio header shows no specimen MPa / °C numbers", () => {
  const markup = renderToStaticMarkup(<CALPHADMultiComponentStudio />);
  const start = markup.indexOf("Active Material Specimen:");
  assert.ok(start >= 0);
  const banner = markup.slice(start, markup.indexOf("</p>", start));
  assert.match(banner, /data-testid="calphad-specimen-properties-unavailable"/);
  assert.doesNotMatch(textOf(banner), /\d+(\.\d+)?\s*(MPa|°C)/);
  assert.match(textOf(banner), /unavailable \(not computed from composition\)/);
});

test("unit converters load no stress from a composition-only specimen", () => {
  assert.deepEqual(specimenStrengthsToLoad(useMaterialStore.getInitialState().activeMaterialSpecimen), { yieldMpa: null, utsMpa: null });
  assert.deepEqual(specimenStrengthsToLoad({ yieldStrength_25C_MPa: null, uts_25C_MPa: undefined }), { yieldMpa: null, utsMpa: null });
  assert.deepEqual(specimenStrengthsToLoad({ yieldStrength_25C_MPa: 0, uts_25C_MPa: Number.NaN }), { yieldMpa: null, utsMpa: null });
  assert.deepEqual(specimenStrengthsToLoad({ yieldStrength_25C_MPa: 1034, uts_25C_MPa: 1241 }), { yieldMpa: 1034, utsMpa: 1241 });
});

test("Digital Twin Hub pull: null mechanicals and no stale designation; push: twin designation is user-sourced", () => {
  const prev = DEFAULT_DIGITAL_TWINS.find((t) => /N07718/.test(t.standardDesignation))!;
  assert.ok(prev);
  const specimen: MaterialSpecimen = {
    ...useMaterialStore.getInitialState().activeMaterialSpecimen,
    metadata: { ...useMaterialStore.getInitialState().activeMaterialSpecimen.metadata, standardDesignation: "" },
  };
  const pulled = twinFromMaterialSpecimen(prev, specimen);
  assert.equal(pulled.mechanical.yieldStrengthMpa, null);
  assert.equal(pulled.mechanical.ultimateTensileStrengthMpa, null);
  assert.equal(pulled.mechanical.elongationPct, null);
  assert.equal(pulled.standardDesignation, "Unresolved", "store '' must not keep the twin's old designation");
  assert.deepEqual(pulled.chemistry.nominalComposition, specimen.composition);

  const withDesignation = twinFromMaterialSpecimen(prev, {
    ...specimen,
    metadata: { ...specimen.metadata, standardDesignation: "Lab ref 12" },
  });
  assert.equal(withDesignation.standardDesignation, "Lab ref 12");

  assert.deepEqual(designationPatchFromTwin({ standardDesignation: "UNS N07718 / AMS 5662" }), {
    standardDesignation: "UNS N07718 / AMS 5662",
    standardDesignationSource: "user",
  });
  assert.deepEqual(designationPatchFromTwin({ standardDesignation: "Unresolved" }), {
    standardDesignation: "",
    standardDesignationSource: undefined,
  });

  // Store round trip: a catalogue preset followed by a twin push is no longer labelled catalogue.
  useMaterialStore.getState().loadPreset("in718");
  useMaterialStore.getState().updateComposition(
    { ...MATERIAL_PRESETS.in718.composition, Nb: 4 },
    "Twin sample",
    designationPatchFromTwin({ standardDesignation: "Twin designation" }),
    "Digital Twin Hub"
  );
  const m = useMaterialStore.getState().activeMaterialSpecimen.metadata;
  assert.equal(m.standardDesignation, "Twin designation");
  assert.equal(m.standardDesignationSource, "user");
});

test("Send-to-module modal shows 'unavailable' for null yield / Ac3 / temperatures (no 910 °C fallback)", () => {
  assert.equal(mpaOrUnavailable(null), "unavailable");
  assert.equal(celsiusOrUnavailable(undefined), "unavailable");
  const base = createPipelinePayloadFromMaterialSpec(MATERIALS_DATABASE.find((m) => /Inconel 718/.test(m.name))!);
  const payload: PipelineMaterialPayload = {
    ...base,
    yieldStrength: null,
    tensileStrength: null,
    icmeProfile: { ...base.icmeProfile, liquidusTemp_C: null, solidusTemp_C: null, solvusTemp_C: null, criticalAc3_C: undefined },
  };
  const text = textOf(renderToStaticMarkup(<SendToModuleModal isOpen onClose={() => {}} payload={payload} />));
  assert.match(text, /σy: unavailable/);
  assert.match(text, /Ac3: unavailable/);
  assert.match(text, /unavailable \/ unavailable/);
  assert.doesNotMatch(text, /910/);
  assert.doesNotMatch(text, /twin/i);
});

test("store-published pipeline payloads never carry a pseudo-standard or the removed constants", () => {
  const storage = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: (k: string) => storage.get(k) ?? null,
      setItem: (k: string, v: string) => void storage.set(k, v),
      removeItem: (k: string) => void storage.delete(k),
      clear: () => storage.clear(),
      key: () => null,
      length: 0,
    },
  });
  const check = (label: string, expectedStandard: string) => {
    const p = getActivePipelineMaterial() as any;
    assert.ok(p, label);
    assert.equal(p.standard, expectedStandard, label);
    assert.doesNotMatch(JSON.stringify(p), /Universal (Specimen )?Thread|Universal Digital Specimen|ASTM E8 \/ E384/, label);
    assert.equal(p.kineticProfile.hallPetch_ky_MPa_um05, null, label);
    assert.equal(p.hardnessProfile.fractureToughness_K1c_MPa_sqrt_m, null, label);
    assert.equal(p.hardnessProfile.estimatedK1c_MPam05, null, label);
    assert.equal(p.hardnessProfile.anisotropyFactors, null, label);
  };

  useMaterialSpecimenStore.getState().updateComposition({ Ni: 60, Cr: 20, Fe: 20 }, "Specimen fixture");
  check("specimen store", "");

  useMaterialStore.getState().loadPreset("custom-ni-superalloy");
  useMaterialStore.getState().updateComposition({ Ni: 60, Cr: 20, Fe: 20 }, "Builder fixture");
  check("material store, no designation", "");

  useMaterialStore.getState().loadPreset("ti64-gr5");
  check("material store, catalogue preset", MATERIAL_PRESETS["ti64-gr5"].standard);
});

test("material-store LPBF fields mirror the specimen-store derivation", () => {
  const compositions: Array<Record<string, number>> = [
    ...Object.values(SPECIMEN_PRESETS).map((p) => p.composition),
    { Fe: 100 },
    { Al: 90, Si: 10 },
    { Ti: 90, Al: 6, V: 4 },
    { Cu: 99, Cr: 1 },
  ];
  for (const c of compositions) {
    const mirror = deriveProperties(c).lpbf as unknown as Record<string, unknown>;
    const source = deriveSpecimenProperties(c).lpbf as unknown as Record<string, unknown>;
    assert.ok(Object.keys(mirror).length > 0);
    // Every LPBF field the material store keeps is the specimen store's value (the specimen store has more fields).
    for (const key of Object.keys(mirror)) assert.deepEqual(mirror[key], source[key], `${JSON.stringify(c)} ${key}`);
  }
});
