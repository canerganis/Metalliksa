import { create } from "zustand";
import { useMaterialStore, withHardnessEstimate, type MaterialSpecimen } from "../store/useMaterialStore";
import { useMaterialSpecimenStore, deriveSpecimenProperties, type ActiveSpecimenState, type BaseMetalType } from "../store/useMaterialSpecimenStore";
import { subscribeToPipelineMaterial, type PipelineMaterialPayload } from "../utils/materialDataPipeline";
import { materialProfileIdentity } from "../utils/materialProfileIdentity";
import { normalizeMaterialCategory } from "../utils/materialCategory";

export const useMaterialContextBridgeStore = create<{message:string;error:boolean}>(()=>({message:"",error:false}));
const identity = (material:{name:string;composition:Record<string,number>;unit?:string},base:string) => JSON.stringify([material.unit,materialProfileIdentity(material.name,base,material.composition)]);
const processKeys = ["laserPower_W","scanSpeed_mms","hatch_um","layer_um","beamDiameter_um","preheatTemp_C","scanStrategy","beamProfile","cadAssetName","specimenDoi","processSeed","inclineAngle_deg","downskinOverhang_deg"] as const;
let applying = false;
let stopActive: (()=>void) | undefined;
let consumers = 0;

function reject(message:string): false {
  useMaterialContextBridgeStore.setState({message,error:true});
  return false;
}

function mirrorSharedMaterial(shared:ActiveSpecimenState): void {
  if (shared.unit!=="wt_pct") {reject("Shared composition is in atomic percent. Alloy Builder's weight-percent estimates are unavailable until an explicit unit conversion is supplied.");return;}
  const previous=useMaterialStore.getState().activeMaterialSpecimen;
  if(identity(previous,previous.metadata.baseMetal)===identity(shared,shared.baseMetal)) {
    // Older persisted profiles used generated labels absent from the builder selector.
    const category=normalizeMaterialCategory(previous.metadata.category,previous.metadata.baseMetal);
    if(category!==previous.metadata.category) {
      const normalized={...previous,metadata:{...previous.metadata,category}};
      useMaterialStore.setState({activeMaterialSpecimen:normalized,activeSpecimen:normalized});
    }
    return;
  }
  // HV is not mirrored by the old unsourced YS/3.1 rule: withHardnessEstimate below gives the labelled steel-only
  // estimate (Pavlina & Van Tyne 2008) or Unavailable.
  const mirrored:MaterialSpecimen=withHardnessEstimate({
    ...previous,id:shared.id,name:shared.name,chemicalFormula:shared.chemicalFormula,composition:{...shared.composition},unit:shared.unit,
    liquidus_C:shared.liquidus_C,solidus_C:shared.solidus_C,freezingRange_C:shared.freezingRange_C,solvus_C:shared.solvus_C,stablePhases:shared.stablePhases,
    yieldStrength_25C_MPa:shared.yieldStrength_25C_MPa,uts_25C_MPa:shared.uts_25C_MPa,youngsModulus_GPa:shared.youngsModulus_GPa,elongation_pct:shared.elongation_pct,
    hardness_HV:null,lpbf:{...shared.lpbf},xrd:{...shared.xrd},
    sourceTab:shared.sourceTab,lastModified:shared.lastModified,isCustomModified:shared.isCustomModified,
    metadata:{...previous.metadata,id:shared.id,serialNumber:"",category:normalizeMaterialCategory(shared.category,shared.baseMetal),baseMetal:shared.baseMetal,density_gcm3:shared.density_gcm3,
      standardDesignation:"",standardDesignationSource:undefined,condition:"Unspecified",manufacturingRoute:"Unspecified",
      source:shared.materialTransfer?.sourceModule||shared.sourceTab,notes:"Shared material context. No standard designation is inferred and no composition-derived temperatures or strengths are held; no experimental validation is implied.",lastModified:shared.lastModified},
  });
  useMaterialStore.setState({activeMaterialSpecimen:mirrored,activeSpecimen:mirrored});
}

interface TransferIdentity {name:string;composition:Record<string,number>;unit?:string;baseMetal:BaseMetalType;sourceModule:string;sourceRecordId:string;interpretation?:string}
function applyIdentity(transfer:TransferIdentity): boolean {
  if(applying)return false;
  if(transfer.unit!=="wt_pct")return reject(transfer.unit==="at_pct"?"Material transfer paused: atomic-percent composition cannot be interpreted by weight-percent property models. Supply an explicit conversion; the shared LPBF material remains unchanged.":"Material transfer paused: composition unit is missing. Specify wt% or provide an explicit conversion before sharing this material.");
  if(!transfer.name?.trim()||!transfer.composition||!Object.keys(transfer.composition).length||Object.entries(transfer.composition).some(([element,value])=>!element.trim()||typeof value!=="number"||!Number.isFinite(value)||value<0)||Object.values(transfer.composition).reduce((sum,value)=>sum+value,0)<=0)return reject("Material transfer paused: a named composition with finite, nonnegative values and a positive total is required.");
  const current=useMaterialSpecimenStore.getState().activeSpecimen;
  if(identity(current,current.baseMetal)===identity(transfer,transfer.baseMetal))return true;
  applying=true;
  try {
    const liveProcess=Object.fromEntries(processKeys.map(key=>[key,current.lpbf[key]]));
    // Derive with the existing model without re-publishing over the original source payload.
    const derived=deriveSpecimenProperties({...transfer.composition},transfer.name,transfer.baseMetal);
    const shared:ActiveSpecimenState={...derived,id:materialProfileIdentity(transfer.name,transfer.baseMetal,transfer.composition),sourceTab:`${transfer.sourceModule} · composition transfer`,lastModified:Date.now(),isCustomModified:true,unit:"wt_pct",lpbf:{...derived.lpbf,...liveProcess},materialTransfer:{sourceModule:transfer.sourceModule,sourceRecordId:transfer.sourceRecordId,compositionInterpretation:transfer.interpretation||"nominal",resultType:"Screening only",note:"Only material identity and composition were transferred. No properties are derived from composition; source property values and confidence were not promoted."}};
    useMaterialSpecimenStore.setState({activeSpecimen:shared});
    mirrorSharedMaterial(shared);
    useMaterialContextBridgeStore.setState({error:false,message:`Shared material: ${shared.name}. ${transfer.interpretation==="range-midpoint"?"Composition ranges are represented by nominal midpoints. ":""}LPBF process settings retained; no properties are derived from composition.`});
    return true;
  } finally {applying=false;}
}

/** Live explicit transfers only; no persisted pipeline payload is replayed. */
export function transferPipelineMaterial(payload:PipelineMaterialPayload): boolean {
  return applyIdentity({name:payload.name,composition:payload.composition,unit:payload.compositionUnit,baseMetal:payload.baseMetal,sourceModule:payload.sourceModule,sourceRecordId:payload.id,interpretation:payload.compositionInterpretation});
}

/** Install once at the app root. Canonical shared material is authoritative on startup. */
export function startMaterialContextBridge(): ()=>void {
  consumers++;
  if(!stopActive){
    applying=true;
    try{mirrorSharedMaterial(useMaterialSpecimenStore.getState().activeSpecimen);}finally{applying=false;}
    let builderHydrating=false;
    const offHydrate=useMaterialStore.persist?.onHydrate(()=>{builderHydrating=true;}) ?? (()=>{});
    const offFinish=useMaterialStore.persist?.onFinishHydration(()=>{builderHydrating=false;applying=true;try{mirrorSharedMaterial(useMaterialSpecimenStore.getState().activeSpecimen);}finally{applying=false;}}) ?? (()=>{});
    const offBuilder=useMaterialStore.subscribe((state,previous)=>{
      if(applying||builderHydrating)return;
      const material=state.activeMaterialSpecimen;
      if(identity(material,material.metadata.baseMetal)===identity(previous.activeMaterialSpecimen,previous.activeMaterialSpecimen.metadata.baseMetal))return;
      applyIdentity({name:material.name,composition:material.composition,unit:material.unit,baseMetal:material.metadata.baseMetal,sourceModule:"Alloy Builder",sourceRecordId:material.id});
    });
    const offShared=useMaterialSpecimenStore.subscribe((state,previous)=>{
      if(applying||identity(state.activeSpecimen,state.activeSpecimen.baseMetal)===identity(previous.activeSpecimen,previous.activeSpecimen.baseMetal))return;
      applying=true;try{mirrorSharedMaterial(state.activeSpecimen);}finally{applying=false;}
    });
    const offPipeline=subscribeToPipelineMaterial(payload=>{if(payload&&!applying)transferPipelineMaterial(payload);});
    stopActive=()=>{offBuilder();offShared();offPipeline();offHydrate();offFinish();};
  }
  let stopped=false;
  return ()=>{if(stopped)return;stopped=true;consumers--;if(consumers===0){stopActive?.();stopActive=undefined;}};
}
