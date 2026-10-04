import assert from "node:assert/strict";
import {afterEach,test} from "node:test";
import {useMaterialStore} from "../src/store/useMaterialStore";
import {useMaterialSpecimenStore} from "../src/store/useMaterialSpecimenStore";
import {startMaterialContextBridge,transferPipelineMaterial,useMaterialContextBridgeStore} from "../src/services/materialContextBridge";
import {setActivePipelineMaterial,type PipelineMaterialPayload} from "../src/utils/materialDataPipeline";
import {MATERIAL_CATEGORIES} from "../src/utils/materialCategory";

let stop:(()=>void)|undefined;
afterEach(()=>{stop?.();stop=undefined;});

test("startup mirrors authoritative shared material into builder without applying stale legacy material",()=>{
  useMaterialStore.getState().loadPreset("inconel-718");
  useMaterialSpecimenStore.getState().loadPreset("ss-316l");
  const shared=useMaterialSpecimenStore.getState().activeSpecimen;
  const saved=useMaterialStore.getState().savedSpecimens;
  stop=startMaterialContextBridge();
  assert.equal(useMaterialSpecimenStore.getState().activeSpecimen,shared);
  assert.equal(useMaterialStore.getState().activeMaterialSpecimen.name,shared.name);
  assert.deepEqual(useMaterialStore.getState().activeMaterialSpecimen.composition,shared.composition);
  assert.equal(useMaterialStore.getState().activeMaterialSpecimen.metadata.category,"Steels & Irons");
  assert.equal(useMaterialStore.getState().savedSpecimens,saved);
  // The mirror used HV = round(YS / 3.1) for any alloy; an austenitic 316L now gets no HV, with the reason.
  const mirrored=useMaterialStore.getState().activeMaterialSpecimen;
  assert.equal(mirrored.hardness_HV,null);
  assert.equal(mirrored.hardnessHVStatus,"unavailable");
  assert.match(mirrored.hardnessHVNote??"",/^Unavailable: no verified hardness-strength relation for this alloy class \(Austenitic stainless steel\)/);
});

test("all shared base families have selectable categories and legacy persisted labels normalize without losing metadata",()=>{
  for(const [base,category] of Object.entries(MATERIAL_CATEGORIES)) {
    useMaterialSpecimenStore.getState().updateComposition({[base === "Other" || base === "Refractory" ? "W" : base]:100},`Synthetic ${base} UI fixture`,base as keyof typeof MATERIAL_CATEGORIES);
    assert.equal(useMaterialSpecimenStore.getState().activeSpecimen.category,category);
  }
  useMaterialSpecimenStore.getState().loadPreset("ss-316l");
  useMaterialSpecimenStore.getState().updateLpbfProcess({laserPower_W:40,scanSpeed_mms:850});
  stop=startMaterialContextBridge();
  stop();stop=undefined;
  useMaterialStore.getState().updateMetadata({category:"Fe-Base Alloy",notes:"Preserve fixture provenance",source:"Synthetic UI fixture"});
  const process=useMaterialSpecimenStore.getState().activeSpecimen.lpbf;
  stop=startMaterialContextBridge();
  const metadata=useMaterialStore.getState().activeMaterialSpecimen.metadata;
  assert.equal(metadata.category,"Steels & Irons");
  assert.equal(metadata.notes,"Preserve fixture provenance");
  assert.equal(metadata.source,"Synthetic UI fixture");
  assert.equal(useMaterialSpecimenStore.getState().activeSpecimen.lpbf,process);
  assert.equal(process.laserPower_W,40);
  assert.equal(process.recommendedLaserPower_W,200);
});

test("builder composition edits propagate stable material identity and preserve every process setting",()=>{
  useMaterialSpecimenStore.getState().loadPreset("ss-316l");
  useMaterialSpecimenStore.getState().updateLpbfProcess({laserPower_W:333,scanSpeed_mms:875,hatch_um:91,layer_um:35,processSeed:871,inclineAngle_deg:12,downskinOverhang_deg:23,cadAssetName:"fixture.stl",specimenDoi:"fixture-source"});
  const previous=useMaterialSpecimenStore.getState().activeSpecimen.lpbf;
  stop=startMaterialContextBridge();
  useMaterialStore.getState().updateComposition({Ni:70,Cr:30},"Custom fixture alloy");
  const current=useMaterialSpecimenStore.getState().activeSpecimen;
  assert.equal(current.name,"Custom fixture alloy");
  assert.deepEqual(current.composition,{Ni:70,Cr:30});
  for(const key of ["laserPower_W","scanSpeed_mms","hatch_um","layer_um","beamDiameter_um","preheatTemp_C","scanStrategy","beamProfile","cadAssetName","specimenDoi","processSeed","inclineAngle_deg","downskinOverhang_deg"] as const)assert.equal(current.lpbf[key],previous[key],key);
  assert.equal(current.materialTransfer?.resultType,"Screening only");
  assert.match(current.id,/material-profile:/);
  const id=current.id;
  useMaterialStore.getState().updateComposition({Cr:30,Ni:70},"Custom fixture alloy");
  assert.equal(useMaterialSpecimenStore.getState().activeSpecimen.id,id);
});

test("pipeline identity transfer synchronizes both views, declares nominal midpoints and ignores confidence upgrades",()=>{
  stop=startMaterialContextBridge();
  // Identity-only fixture deliberately supplies no material property table or validation evidence.
  const payload={id:"catalog-fixture",name:"AlSi10Mg fixture",composition:{Al:90,Si:10},compositionUnit:"wt_pct",compositionInterpretation:"range-midpoint",baseMetal:"Al",sourceModule:"Materials Database",yieldStrength:999999} as unknown as PipelineMaterialPayload;
  assert.equal(transferPipelineMaterial(payload),true);
  const shared=useMaterialSpecimenStore.getState().activeSpecimen;
  assert.equal(shared.name,payload.name);
  assert.equal(useMaterialStore.getState().activeMaterialSpecimen.name,payload.name);
  assert.notEqual(shared.yieldStrength_25C_MPa,999999);
  assert.equal(shared.materialTransfer?.sourceRecordId,"catalog-fixture");
  assert.match(useMaterialContextBridgeStore.getState().message,/nominal midpoints/);
});

test("atomic-percent and missing-unit transfers cannot overwrite or reinterpret the shared wt% specimen",()=>{
  useMaterialSpecimenStore.getState().loadPreset("inconel-718");
  stop=startMaterialContextBridge();
  const shared=useMaterialSpecimenStore.getState().activeSpecimen;
  const payload={id:"atomic-fixture",name:"Atomic fixture alloy",composition:{Ni:50,Al:50},compositionUnit:"at_pct",baseMetal:"Ni",sourceModule:"Import"} as unknown as PipelineMaterialPayload;
  assert.equal(transferPipelineMaterial(payload),false);
  assert.equal(useMaterialSpecimenStore.getState().activeSpecimen,shared);
  assert.equal(useMaterialContextBridgeStore.getState().error,true);
  assert.match(useMaterialContextBridgeStore.getState().message,/atomic-percent/);
  assert.equal(transferPipelineMaterial({...payload,compositionUnit:undefined}),false);
  assert.equal(useMaterialSpecimenStore.getState().activeSpecimen,shared);
  useMaterialStore.getState().setActiveMaterialSpecimen({unit:"at_pct"});
  useMaterialStore.getState().updateComposition({Ni:40,Al:60},"Atomic editing fixture");
  assert.equal(useMaterialStore.getState().activeMaterialSpecimen.unit,"at_pct");
  assert.equal(useMaterialSpecimenStore.getState().activeSpecimen,shared);
});

test("shared preset changes refresh builder, while process edits do not overwrite builder metadata",()=>{
  useMaterialSpecimenStore.getState().loadPreset("inconel-718");
  stop=startMaterialContextBridge();
  useMaterialSpecimenStore.getState().loadPreset("ti-6al-4v");
  const mirrored=useMaterialStore.getState().activeMaterialSpecimen;
  assert.equal(mirrored.name,useMaterialSpecimenStore.getState().activeSpecimen.name);
  useMaterialSpecimenStore.getState().updateLpbfProcess({laserPower_W:222});
  assert.equal(useMaterialStore.getState().activeMaterialSpecimen,mirrored);
});

test("live Send to Module events reach shared context without recursive pipeline publication",()=>{
  const originalWindow=Object.getOwnPropertyDescriptor(globalThis,"window");
  const target=new EventTarget();
  Object.defineProperty(globalThis,"window",{value:target,configurable:true});
  try {
    let events=0;
    target.addEventListener("metallix-pipeline-updated",()=>events++);
    stop=startMaterialContextBridge();
    const payload={id:"live-fixture",name:"Live transfer fixture alloy",composition:{Ni:75,Cr:25},compositionUnit:"wt_pct",baseMetal:"Ni",sourceModule:"Materials Database"} as unknown as PipelineMaterialPayload;
    setActivePipelineMaterial(payload);
    assert.equal(useMaterialSpecimenStore.getState().activeSpecimen.name,payload.name);
    assert.equal(useMaterialStore.getState().activeMaterialSpecimen.name,payload.name);
    assert.equal(events,1,"The explicit source payload must not be overwritten or recursively re-published by the bridge");
  } finally {
    stop?.();stop=undefined;
    if(originalWindow)Object.defineProperty(globalThis,"window",originalWindow);else delete (globalThis as {window?:unknown}).window;
  }
});
