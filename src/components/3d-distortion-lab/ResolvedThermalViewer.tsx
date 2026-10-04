import { useWorkspaceVisible } from '../WorkspaceVisibility';
import { useVisibleAnimationFrame } from '../../hooks/useVisibleAnimationFrame';
import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { liquidusSection, thermalColour } from "./thermalFieldGeometry";
import { SimulationResult } from "../../services/lpbfSimulationService";

interface Frame { path: string; time_s: number; surface_m: number; minimum_K: number; maximum_K: number; geometry?: {angle_rad:number;along_m:[number,number];across_m:[number,number];bottom_m:number} }
interface Series { version: number; cells: number; spacing_m: number; coordinates: string; solidus_K: number; liquidus_K: number; boiling_K?: number; frames: Frame[] }
export function parseFieldSeries(value: unknown): Series {
  const s = value as Series;
  if (!s || s.version !== 1 || !Number.isInteger(s.cells) || s.cells < 1 || s.cells > 600000 || s.coordinates !== "field-coordinates.bin"
    || !Number.isFinite(s.spacing_m) || s.spacing_m <= 0 || !Number.isFinite(s.solidus_K) || !Number.isFinite(s.liquidus_K) || s.solidus_K <= 0 || s.liquidus_K <= s.solidus_K
    || !Array.isArray(s.frames) || !s.frames.length || s.frames.length > 128 || !s.frames.every((f,i) => f && f.path === `field-frame-${String(i).padStart(3,"0")}.bin`
      && [f.time_s,f.surface_m,f.minimum_K,f.maximum_K].every(Number.isFinite) && f.time_s >= 0 && f.minimum_K > 0 && f.maximum_K >= f.minimum_K && (!i || f.time_s > s.frames[i-1].time_s))) throw new Error("Invalid resolved field series");
  if(s.boiling_K!==undefined&&(!Number.isFinite(s.boiling_K)||s.boiling_K<=s.liquidus_K))throw new Error("Invalid boiling threshold");
  for(const frame of s.frames){const g=frame.geometry;if(g&&(!Number.isFinite(g.angle_rad)||!Number.isFinite(g.bottom_m)||g.bottom_m>frame.surface_m||![g.along_m,g.across_m].every(v=>Array.isArray(v)&&v.length===2&&v.every(Number.isFinite)&&v[1]>=v[0])))throw new Error("Invalid frame geometry");}
  return s;
}
export function decodeField(buffer: ArrayBuffer, count: number): Float32Array {
  if (buffer.byteLength !== count*4) throw new Error("Truncated or oversized field artifact");
  const view = new DataView(buffer), values = new Float32Array(count);
  for(let i=0;i<count;i++){values[i]=view.getFloat32(i*4,true);if(!Number.isFinite(values[i]))throw new Error("Nonfinite field artifact");}
  return values;
}
export function ResolvedThermalViewer({jobId,result,onTimeChange}:{jobId:string;result?:SimulationResult;onTimeChange?:(time:number)=>void}) {
  const workspaceVisible=useWorkspaceVisible();
  const frameRef=useRef<(()=>void)|null>(null);
  useVisibleAnimationFrame(()=>frameRef.current?.());
  const resetVersion=useRef(0);
  const cameraState=useRef<{position:THREE.Vector3;target:THREE.Vector3} | undefined>(undefined);
  const rendererRef=useRef<THREE.WebGLRenderer | undefined>(undefined);
  useEffect(()=>()=>{rendererRef.current?.dispose();rendererRef.current?.forceContextLoss();rendererRef.current?.domElement.remove();rendererRef.current=undefined;},[]);
  const host = useRef<HTMLDivElement>(null);
  const [series,setSeries]=useState<Series>(); const [coordinates,setCoordinates]=useState<Float32Array>();
  const [values,setValues]=useState<Float32Array>(); const [index,setIndex]=useState(0);
  const [loadedIndex,setLoadedIndex]=useState(-1); const [quantity,setQuantity]=useState("temperature");
  const [section,setSection]=useState(100); const [hotOnly,setHotOnly]=useState(false);
  const [view,setView]=useState("isometric"); const [normal,setNormal]=useState<0|1|2>(1);
  const [contour,setContour]=useState(true);
  const [dimensions,setDimensions]=useState(true);
  const [wireframe,setWireframe]=useState(false); const [rotate,setRotate]=useState(false);
  const [playing,setPlaying]=useState(false); const [error,setError]=useState("");
  const [visible,setVisible]=useState(0); const [reset,setReset]=useState(0);
  const base=`/api/lpbf/jobs/${jobId}/artifacts/`;
  useEffect(()=>{if(series&&loadedIndex>=0)onTimeChange?.(series.frames[loadedIndex].time_s);},[series,loadedIndex,onTimeChange]);
  useEffect(()=>{
    const abort=new AbortController();cameraState.current=undefined;setSeries(undefined);setValues(undefined);setCoordinates(undefined);setIndex(0);setLoadedIndex(-1);setError("");setPlaying(false);
    const get=async(name:string)=>{const r=await fetch(base+name,{signal:abort.signal});if(!r.ok)throw new Error(`Field artifact HTTP ${r.status}`);return r;};
    (async()=>{const s=parseFieldSeries(await (await get("field-series.json")).json());const c=decodeField(await (await get(s.coordinates)).arrayBuffer(),s.cells*3);if(!abort.signal.aborted){setSeries(s);setCoordinates(c);setIndex(s.frames.reduce((best,f,i)=>f.maximum_K>s.frames[best].maximum_K?i:best,0));}})().catch(e=>{if(!abort.signal.aborted)setError(e.message);});
    return()=>abort.abort();
  },[base]);
  useEffect(()=>{
    if(!series)return;const abort=new AbortController();setError("");
    fetch(base+series.frames[index].path,{signal:abort.signal}).then(async r=>{if(!r.ok)throw new Error(`Field frame HTTP ${r.status}`);const v=decodeField(await r.arrayBuffer(),series.cells);if(v.some(t=>t<=0))throw new Error("Nonphysical temperature");if(!abort.signal.aborted){setValues(v);setLoadedIndex(index);}}).catch(e=>{if(!abort.signal.aborted){setError(e.message);setPlaying(false);}});
    return()=>abort.abort();
  },[series,index,base]);
  useEffect(()=>{if(!workspaceVisible||!playing||!series||loadedIndex!==index)return;const timer=setTimeout(()=>{if(index===series.frames.length-1)setPlaying(false);else setIndex(index+1);},200);return()=>clearTimeout(timer);},[workspaceVisible,playing,series,index,loadedIndex]);
  useEffect(()=>{
    if(!workspaceVisible||!host.current||!series||!coordinates||!values||loadedIndex<0)return;
    const element=host.current;let renderer:THREE.WebGLRenderer;
    try{renderer=rendererRef.current ?? new THREE.WebGLRenderer({antialias:true});rendererRef.current=renderer;}catch{setError("WebGL unavailable. Download the field artifacts or use the resolved X–Z slices.");return;}
    renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));element.appendChild(renderer.domElement);
    renderer.domElement.setAttribute("aria-label","Resolved 3D thermal cell field. Arrow keys pan; use reset camera to restore the view.");
    renderer.domElement.tabIndex=0;
    const scene=new THREE.Scene();scene.background=new THREE.Color("#080f1c");
    const camera=new THREE.PerspectiveCamera(40,1,.1,100000);
    const bounds=new THREE.Box3();for(let i=0;i<series.cells;i++)bounds.expandByPoint(new THREE.Vector3(coordinates[i*3]*1e6,coordinates[i*3+1]*1e6,coordinates[i*3+2]*1e6));
    const center=bounds.getCenter(new THREE.Vector3()),extent=bounds.getSize(new THREE.Vector3()).length()+series.spacing_m*1e6;
    camera.up.set(0,0,1);camera.position.copy(center).add(new THREE.Vector3(extent*.9,-extent*1.1,extent*.85));
    if(view==="top"){camera.up.set(0,1,0);camera.position.copy(center).add(new THREE.Vector3(0,0,extent*1.1));}
    if(view==="longitudinal")camera.position.copy(center).add(new THREE.Vector3(0,-extent*1.1,0));
    if(view==="transverse")camera.position.copy(center).add(new THREE.Vector3(extent*1.1,0,0));
    const controls=new OrbitControls(camera,renderer.domElement);controls.target.copy(center);controls.listenToKeyEvents(renderer.domElement);controls.enableDamping=true;controls.autoRotate=rotate;controls.autoRotateSpeed=.5;
    if(resetVersion.current!==reset){cameraState.current=undefined;resetVersion.current=reset;}
    if(cameraState.current){camera.position.copy(cameraState.current.position);controls.target.copy(cameraState.current.target);}
    const frame=series.frames[loadedIndex],globalMax=Math.max(...series.frames.map(f=>f.maximum_K)),globalMin=Math.min(...series.frames.map(f=>f.minimum_K));
    const minNormal=bounds.min.getComponent(normal),maxNormal=bounds.max.getComponent(normal);
    const plane=(minNormal+Math.round((maxNormal-minNormal)*section/100/(series.spacing_m*1e6))*series.spacing_m*1e6)*1e-6;
    // Exact cell cubes up to the display budget; larger domains use explicitly sampled cell cubes.
    const stride=Math.max(1,Math.ceil(series.cells/50000));const positions:number[]=[],colors:number[]=[],mushy:boolean[]=[];const colour=new THREE.Color();
    for(let i=0;i<series.cells;i+=stride){
      const x=coordinates[i*3]*1e6,y=coordinates[i*3+1]*1e6,z=coordinates[i*3+2]*1e6,t=values[i];
      if(coordinates[i*3+2]>=frame.surface_m || coordinates[i*3+normal]>plane+series.spacing_m*.1 || (hotOnly&&t<series.solidus_K))continue;
      const f=Math.max(0,Math.min(1,(t-series.solidus_K)/(series.liquidus_K-series.solidus_K)));
      colour.set(quantity==="phase"?thermalColour(f,0,.5,1,1):thermalColour(t,globalMin,series.solidus_K,series.liquidus_K,globalMax));
      positions.push(x,y,z);colors.push(colour.r,colour.g,colour.b);
      mushy.push(t>=series.solidus_K&&t<series.liquidus_K);
    }
    setVisible(positions.length/3);
    const geometry=new THREE.BoxGeometry(series.spacing_m*1e6,series.spacing_m*1e6,series.spacing_m*1e6);
    const material=new THREE.MeshBasicMaterial({wireframe});const mushyMaterial=new THREE.MeshBasicMaterial({wireframe,transparent:true,opacity:.5,depthWrite:false});
    const mushyCount=mushy.filter(Boolean).length;
    const mesh=new THREE.InstancedMesh(geometry,material,mushy.length-mushyCount), mushyMesh=new THREE.InstancedMesh(geometry,mushyMaterial,mushyCount);const matrix=new THREE.Matrix4();
    let denseIndex=0,mushyIndex=0;
    for(let i=0;i<positions.length/3;i++){const target=mushy[i]?mushyMesh:mesh,j=mushy[i]?mushyIndex++:denseIndex++;matrix.makeTranslation(...positions.slice(i*3,i*3+3) as [number,number,number]);target.setMatrixAt(j,matrix);target.setColorAt(j,new THREE.Color(...colors.slice(i*3,i*3+3) as [number,number,number]));}scene.add(mesh,mushyMesh);
    const cutGeometry=new THREE.PlaneGeometry((normal===0?bounds.max.z-bounds.min.z:bounds.max.x-bounds.min.x)+series.spacing_m*1e6, (normal===1?bounds.max.z-bounds.min.z:bounds.max.y-bounds.min.y)+series.spacing_m*1e6);
    const cutMaterial=new THREE.MeshBasicMaterial({color:0x38bdf8,transparent:true,opacity:.08,side:THREE.DoubleSide,depthWrite:false});
    const cut=new THREE.Mesh(cutGeometry,cutMaterial);cut.position.copy(center);cut.position.setComponent(normal,plane*1e6);
    if(normal===1)cut.rotation.x=Math.PI/2;if(normal===0)cut.rotation.y=Math.PI/2;
    if(section<100)scene.add(cut);
    const contourGeometry=new THREE.BufferGeometry().setAttribute("position",new THREE.Float32BufferAttribute(contour?liquidusSection(coordinates,values,normal,plane,series.spacing_m,frame.surface_m,series.liquidus_K):[],3));
    const contourMaterial=new THREE.LineBasicMaterial({color:0xffe6a3,depthTest:false,transparent:true,opacity:.95});
    const contourLines=new THREE.LineSegments(contourGeometry,contourMaterial);contourLines.renderOrder=10;scene.add(contourLines);
    const dimensionObjects: {geometry:THREE.BufferGeometry;material:THREE.Material;texture?:THREE.Texture}[]=[];
    const g=frame.geometry;
    if(dimensions&&g){
      const point=(a:number,b:number,z:number)=>new THREE.Vector3((a*Math.cos(g.angle_rad)-b*Math.sin(g.angle_rad))*1e6,(a*Math.sin(g.angle_rad)+b*Math.cos(g.angle_rad))*1e6,z*1e6);
      const [a0,a1]=g.along_m,[b0,b1]=g.across_m,offset=series.spacing_m*1.5,z=frame.surface_m;
      const measures:[string,THREE.Vector3,THREE.Vector3][]=[
        ["L",point(a0,b0-offset,z),point(a1,b0-offset,z)],
        ["W",point(a1+offset,b0,z),point(a1+offset,b1,z)],
        ["D",point(a0-offset,b0,g.bottom_m),point(a0-offset,b0,z)]];
      for(const [name,start,end] of measures){
        const geom=new THREE.BufferGeometry().setFromPoints([start,end]),mat=new THREE.LineBasicMaterial({color:0x7dd3fc,depthTest:false});
        const line=new THREE.Line(geom,mat);line.renderOrder=11;scene.add(line);dimensionObjects.push({geometry:geom,material:mat});
        const canvas=document.createElement("canvas");canvas.width=320;canvas.height=64;const ctx=canvas.getContext("2d");
        if(ctx){ctx.fillStyle="#081320";ctx.fillRect(0,0,320,64);ctx.fillStyle="#bae6fd";ctx.font="26px sans-serif";ctx.textAlign="center";ctx.fillText(`${name} ${start.distanceTo(end).toFixed(1)} µm`,160,42);const texture=new THREE.CanvasTexture(canvas);const sm=new THREE.SpriteMaterial({map:texture,depthTest:false});const sprite=new THREE.Sprite(sm);sprite.geometry=sprite.geometry.clone();sprite.position.copy(start).add(end).multiplyScalar(.5);sprite.scale.set(extent*.22,extent*.044,1);sprite.renderOrder=12;scene.add(sprite);dimensionObjects.push({geometry:sprite.geometry,material:sm,texture});}
      }
    }
    const axes=new THREE.AxesHelper(extent*.22);axes.position.copy(bounds.min);scene.add(axes);
    const box=new THREE.Box3Helper(bounds,0x334155);scene.add(box);
    const resize=()=>{const width=Math.max(1,element.clientWidth),height=Math.max(1,element.clientHeight);renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix();};
    const observer=new ResizeObserver(resize);observer.observe(element);resize();let inView=true;
    const visibility=new IntersectionObserver(entries=>{inView=entries[0]?.isIntersecting??false;});visibility.observe(element);
    const render=()=>{if(inView&&!document.hidden){controls.update();renderer.render(scene,camera);}};frameRef.current=render;render();
    return()=>{cameraState.current={position:camera.position.clone(),target:controls.target.clone()};frameRef.current=null;observer.disconnect();visibility.disconnect();controls.dispose();mesh.dispose();mushyMesh.dispose();mushyMaterial.dispose();geometry.dispose();material.dispose();cutGeometry.dispose();cutMaterial.dispose();contourGeometry.dispose();contourMaterial.dispose();dimensionObjects.forEach(o=>{o.geometry.dispose();o.material.dispose();o.texture?.dispose();});axes.geometry.dispose();(axes.material as THREE.Material).dispose();box.geometry.dispose();(box.material as THREE.Material).dispose();renderer.renderLists.dispose();};
  },[workspaceVisible,series,coordinates,values,loadedIndex,quantity,section,hotOnly,reset,wireframe,rotate,view,normal,contour,dimensions]);
  const frame=series?.frames[loadedIndex];
  const activeScan=frame&&result?.scanPath?.find(s=>s.start_s<=frame.time_s&&frame.time_s<s.end_s);
  const lastScan=result?.scanPath?.at(-1);
  const phase=activeScan?`Laser on · layer ${activeScan.layer+1} / track ${(activeScan.track??0)+1}`:frame&&lastScan?frame.time_s<lastScan.end_s+(result?.settings.dwell_s??0)?"Dwell / inter-track interval · jump motion unresolved":"Final cooling":"Scan timing unavailable";
  return <section aria-label="Resolved thermal field explorer" className="overflow-hidden rounded-xl bg-[#080f1c] ring-1 ring-slate-700/70">
    <header className="flex flex-wrap items-center justify-between gap-3 p-4"><div><h4 className="font-semibold">Resolved 3D thermal field</h4><p className="text-xs text-slate-400 mt-1">Actual solver cells · temperature and enthalpy phase fraction · opens at peak-temperature sample</p></div><select aria-label="Field quantity" value={quantity} onChange={e=>setQuantity(e.target.value)} className="bg-slate-800 rounded p-2 text-sm"><option value="temperature">Temperature · K</option><option value="phase">Liquid fraction · 0–1</option></select></header>
    {error&&<p role="alert" className="px-4 text-red-300">{error}</p>}
    <div className="flex flex-wrap gap-2 px-4" aria-label="Field view presets">{["isometric","top","longitudinal","transverse"].map(v=><button key={v} aria-pressed={view===v} className={`rounded-md border px-3 py-2 text-xs capitalize ${view===v?"border-sky-400/50 text-sky-200 bg-sky-400/10":"border-slate-700 text-slate-400"}`} onClick={()=>{setView(v);setNormal(v==="top"?2:v==="transverse"?0:1);setReset(n=>n+1);}}>{v==="longitudinal"?"X–Z":v==="transverse"?"Y–Z":v}</button>)}</div>
    <div ref={host} className="h-[360px] sm:h-[470px] w-full touch-none"/>
    <div className="px-4 pb-4 space-y-3"><div className="flex flex-wrap gap-4 text-xs text-slate-300"><span>{frame?`${(frame.time_s*1000).toFixed(4)} ms · frame ${loadedIndex+1}/${series?.frames.length}`:"Loading resolved fields…"}</span><span>{frame?`Domain peak ${frame.maximum_K.toFixed(1)} K`:""}</span><span>{series?`${visible.toLocaleString("en-US")} displayed / ${series.cells.toLocaleString("en-US")} mesh cells · ${(series.spacing_m*1e6).toFixed(2)} µm`:""}</span></div>
    <div className="flex gap-3 items-center"><button disabled={!series||!!error} onClick={()=>{if(series&&index===series.frames.length-1)setIndex(0);setPlaying(!playing);}} className="rounded bg-sky-700 px-4 py-2 text-sm disabled:opacity-40">{playing?"Pause":"Play"}</button><input aria-label="Simulation time" className="flex-1 accent-sky-400 min-w-0" type="range" min={0} max={(series?.frames.length||1)-1} value={index} onChange={e=>{setPlaying(false);setIndex(Number(e.target.value));}}/><span className="text-xs text-slate-400">{loadedIndex!==index?"Loading frame…":"Sampled time"}</span></div>
    <p role="status" className="text-xs text-sky-200">{phase}</p>
    <label className="block text-xs text-slate-300"><input type="checkbox" checked={dimensions} onChange={e=>setDimensions(e.target.checked)}/> L / W / D guides · current snapshot, all molten cells. Header dimensions belong to the maximum-volume sample.</label>
    <div className="flex flex-wrap items-center gap-4 text-sm"><label className="flex items-center gap-2">{"XYZ"[normal]} section<input aria-label="Section plane" type="range" min="0" max="100" value={section} onChange={e=>setSection(Number(e.target.value))}/>{section}%</label><label><input type="checkbox" checked={contour} onChange={e=>setContour(e.target.checked)}/> Liquidus section contour</label><label><input type="checkbox" checked={hotOnly} onChange={e=>setHotOnly(e.target.checked)}/> Mushy / liquid cells only</label><label><input type="checkbox" checked={wireframe} onChange={e=>setWireframe(e.target.checked)}/> Mesh edges</label><label><input type="checkbox" checked={rotate} onChange={e=>setRotate(e.target.checked)}/> Auto-rotate</label><button className="underline text-slate-300" onClick={()=>{cameraState.current=undefined;setReset(v=>v+1);}}>Reset camera</button></div>
    {series&&<><div className="flex h-2 overflow-hidden rounded" aria-label="Fixed field color scale">{Array.from({length:100},(_,i)=>{const lo=Math.min(...series.frames.map(f=>f.minimum_K)),hi=Math.max(...series.frames.map(f=>f.maximum_K));return <span key={i} className="flex-1" style={{background:quantity==="phase"?thermalColour(i/99,0,.5,1,1):thermalColour(lo+(hi-lo)*i/99,lo,series.solidus_K,series.liquidus_K,hi)}}/>;})}</div><div className="flex flex-wrap gap-x-5 gap-y-2 text-xs tabular-nums text-slate-300"><span>Preheat {result? (result.settings.preheat_C+273.15).toFixed(1):"—"} K</span><span>Solidus {series.solidus_K.toFixed(1)} K</span><span>Liquidus {series.liquidus_K.toFixed(1)} K</span><span>Sampled peak {Math.max(...series.frames.map(f=>f.maximum_K)).toFixed(1)} K</span><span className="text-fuchsia-300/80">Boiling {series.boiling_K?.toFixed(1)||"unavailable"} K · unresolved</span></div></>}
    <p className="text-xs text-slate-400">{quantity==="phase"?"Fixed 0 solid → 1 liquid scale; enthalpy fraction, not a gas interface":"Fixed temperature scale across all frames · blue solid, blue–amber mushy, amber–ivory liquid."} Pale line: linearly reconstructed liquidus on the selected cell-center plane, using all section cells. Cyan plane: section location. No contour means no liquidus crossing on this section. X red · Y green · Z blue. Drag to orbit; scroll to zoom.</p>
    <details className="border-t border-slate-700/60 pt-2 text-xs text-slate-400"><summary className="cursor-pointer">Field source and integrity</summary><p className="mt-2 break-all">{result?.solver.id||"Thermal artifact"} · field-series SHA-256: {result?.artifacts?.find(a=>a.path==="field-series.json")?.sha256||"Unavailable"}</p><p className="mt-2">Cell values are float32 visualization exports of the solver field. The server checks artifact size and checksum. Contours interpolate temperature, not free-surface geometry. Section coordinates follow the mesh axes, not the rotated scan axes.</p></details>
    <p className="text-xs text-amber-200/80">Unvalidated transient thermal · no resolved velocity, keyhole or free surface. {series&&series.cells>50000?`Display samples every ${Math.ceil(series.cells/50000)}th cell; gaps are display sampling, not pores. Full fields remain in artifacts.`:"Uniform cell rendering; no geometric smoothing."} Playback is sampled and slowed for inspection.</p></div>
  </section>;
}
