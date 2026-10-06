import React from "react";
import assert from "node:assert/strict";
import {test} from "node:test";
import {renderToStaticMarkup} from "react-dom/server";
import {AlloyBuilder} from "../src/components/AlloyBuilder";
import {useMaterialStore,deriveProperties,MATERIAL_PRESETS} from "../src/store/useMaterialStore";
import {useMaterialSpecimenStore} from "../src/store/useMaterialSpecimenStore";
import {startMaterialContextBridge} from "../src/services/materialContextBridge";

test("builder renders the selected steel family and distinguishes screening estimate from active process",()=>{
  useMaterialSpecimenStore.getState().loadPreset("ss-316l");
  useMaterialSpecimenStore.getState().updateLpbfProcess({laserPower_W:40,scanSpeed_mms:850});
  const stop=startMaterialContextBridge();
  const builderInitial=useMaterialStore.getInitialState();
  const sharedInitial=useMaterialSpecimenStore.getInitialState();
  const builderOriginal=builderInitial.activeMaterialSpecimen;
  const sharedOriginal=sharedInitial.activeSpecimen;
  // Server rendering reads Zustand's initial snapshots; expose the explicit fixture snapshots.
  builderInitial.activeMaterialSpecimen=useMaterialStore.getState().activeMaterialSpecimen;
  sharedInitial.activeSpecimen=useMaterialSpecimenStore.getState().activeSpecimen;
  try {
    const html=renderToStaticMarkup(<AlloyBuilder/>);
    assert.match(html,/<option value="Steels &amp; Irons" selected="">Steels &amp; Irons<\/option>/);
    assert.doesNotMatch(html,/<option value="Nickel Superalloy" selected/);
    assert.match(html,/<option value="Unspecified" selected="">Unspecified<\/option>/);
    // No per-base-metal "starting estimate" is presented as composition-based: only the user's shared process.
    assert.doesNotMatch(html,/LPBF Starting Estimate|Composition-based estimate/);
    assert.match(html,/Shared LPBF Process \(User Settings\)/);
    assert.match(html,/Current shared process: 40 W @ 850 mm\/s/);
    useMaterialSpecimenStore.getState().updateLpbfProcess({laserPower_W:41});
    sharedInitial.activeSpecimen=useMaterialSpecimenStore.getState().activeSpecimen;
    assert.match(renderToStaticMarkup(<AlloyBuilder/>),/Current shared process: 41 W @ 850 mm\/s/);
    useMaterialStore.getState().updateMetadata({category:"User supplied category"});
    builderInitial.activeMaterialSpecimen=useMaterialStore.getState().activeMaterialSpecimen;
    assert.match(renderToStaticMarkup(<AlloyBuilder/>),/<option value="User supplied category" selected="">User supplied category<\/option>/);
  } finally {
    stop();
    builderInitial.activeMaterialSpecimen=builderOriginal;
    sharedInitial.activeSpecimen=sharedOriginal;
  }
});

const text=(html:string)=>html.replace(/<[^>]+>/g," ").replace(/&amp;/g,"&").replace(/\s+/g," ");

function renderBuilder(): string {
  const builderInitial=useMaterialStore.getInitialState();
  const original=builderInitial.activeMaterialSpecimen;
  builderInitial.activeMaterialSpecimen=useMaterialStore.getState().activeMaterialSpecimen;
  try {return renderToStaticMarkup(<AlloyBuilder/>);} finally {builderInitial.activeMaterialSpecimen=original;}
}

test("builder shows no invented property KPIs: temperatures and strengths are explicitly unavailable",()=>{
  useMaterialStore.getState().updateComposition({Fe:100},"Pure iron fixture");
  const html=renderBuilder();
  const t=text(html);
  // Pure Fe used to show 750 MPa yield (750 + 900 C + ...) and a heuristic liquidus/solidus.
  assert.doesNotMatch(t,/750/);
  assert.doesNotMatch(t,/MPa \(UTS/);
  assert.match(html,/data-testid="alloy-properties-unavailable"/);
  assert.match(t,/Liquidus \/ Solidus, Yield Strength, UTS Unavailable/);
  assert.match(t,/no validated composition-to-property model/);
  // Real computation from the shown composition: inverse rule of mixtures for pure Fe is the Fe elemental density.
  assert.match(t,/7\.874 g\/cm³/);
});

test("builder density is unavailable (no 8.190 or 8.0 fallback) when an element has no tabulated density",()=>{
  useMaterialStore.getState().updateComposition({Ti:89.6,Al:6.1,V:4.1,O:0.2},"Ti fixture with oxygen");
  const t=text(renderBuilder());
  assert.doesNotMatch(t,/8\.190/);
  assert.match(t,/Alloy Density \(Inverse Rule of Mixtures\) Unavailable Unavailable: no tabulated elemental density for O\./);
});

test("builder has no one-tab bar, no unbacked module chips and no live/twin wording",()=>{
  const html=renderBuilder();
  assert.doesNotMatch(html,/Rapid XRD Lab|Specimen Formulator|tab-specimen-studio|Live Shared Store|Broadcasting to|Save Snapshot/);
  assert.doesNotMatch(text(html),/twin|live/i);
  assert.match(html,/data-testid="alloy-shared-with"/);
});

test("standard designation: catalogue preset only, never inferred from composition thresholds",()=>{
  // Any Ni alloy with Nb > 2.5 used to be labelled "UNS N07718 / AMS 5662".
  const d=deriveProperties({Ni:90,Nb:5,Cr:5},"Ni-Nb fixture");
  assert.equal(d.metadata.standardDesignation,"");
  for(const comp of [{Ni:80,Al:3,Ti:3,Cr:14},{Ni:80,Cr:20},{Ti:90,Al:6,V:4},{Fe:70,Cr:18,Ni:12},{Fe:99,C:0.4,Cr:0.6},{Al:90,Si:10}]) {
    assert.equal(deriveProperties(comp,"fixture").metadata.standardDesignation,"",JSON.stringify(comp));
  }
  // Picking the catalogue preset sets its designation...
  useMaterialStore.getState().loadPreset("in718");
  let m=useMaterialStore.getState().activeMaterialSpecimen.metadata;
  assert.equal(m.standardDesignation,MATERIAL_PRESETS.in718.standard);
  assert.equal(m.standardDesignationSource,"catalogue");
  // ...and editing the composition away from the catalogue alloy clears it.
  useMaterialStore.getState().setElement("Nb",3);
  m=useMaterialStore.getState().activeMaterialSpecimen.metadata;
  assert.equal(m.standardDesignation,"");
  assert.equal(m.standardDesignationSource,undefined);
  // A designation the user types is the user's and survives composition edits.
  useMaterialStore.getState().updateMetadata({standardDesignation:"User reference X"});
  assert.equal(useMaterialStore.getState().activeMaterialSpecimen.metadata.standardDesignationSource,"user");
  useMaterialStore.getState().setElement("Nb",4);
  assert.equal(useMaterialStore.getState().activeMaterialSpecimen.metadata.standardDesignation,"User reference X");
  // The default example preset is not a catalogue alloy and carries none.
  assert.equal(MATERIAL_PRESETS["custom-ni-superalloy"].standard,"");
});
