import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { createHash } from "node:crypto";
import { renderToStaticMarkup } from "react-dom/server";
import { LpbfRunReportExport, RunReportButtons } from "../src/components/LpbfRunReportExport";
import { useMaterialSpecimenStore } from "../src/store/useMaterialSpecimenStore";
import { LPBF_ENGINEERING_DEFAULTS, engineeringSignature, type LpbfEngineeringState } from "../src/store/useLpbfEngineeringStore";
import type { LpbfBuildContext } from "../src/store/useLpbfWorkflowStore";
import { createLpbfQualificationReport, sharedSimulationInput } from "../src/utils/lpbfQualificationReport";
import { buildLpbfRunReportHtml, runReportFileName, serializeLpbfRunReportDossier, sha256Hex } from "../src/utils/lpbfRunReport";
import type { SimulationJob, SimulationResult } from "../src/services/lpbfSimulationService";
import type { PythonLpbfBuildJobResult } from "../src/services/pythonComputationService";

// Synthetic presentation fixtures, never physical evidence.
const CREATED = "2026-01-02T03:04:05.000Z";
const specimen = () => useMaterialSpecimenStore.getState().activeSpecimen;
const context = (patch: Partial<LpbfBuildContext> = {}): LpbfBuildContext => ({buildId:"B-17",machine:"M1",powderLot:"L9",powderCondition:"",heatTreatment:"",measurementMethod:"",notes:"",...patch});
const baseEngineering = (): LpbfEngineeringState => ({settings:{...LPBF_ENGINEERING_DEFAULTS},mode:"standard",job:undefined,error:"",busy:false,material:"",properties:"",measurements:"",specimen:"",uncertainty:"",holdout:"unknown",width:"",depth:"",source:"",submittedSignature:"",resultSignature:"",submittedInput:undefined});
function completedJob(): SimulationJob {
  const input = sharedSimulationInput(specimen());
  const result: SimulationResult = {
    schemaVersion:1,requestedMode:"standard",effectiveMode:"screening",solver:{id:"synthetic-report-fixture",version:"v-fixture",openfoam:null},
    settings:input,confidence:"low",validationStatus:"unvalidated",productionReady:false,label:"Unvalidated thermal simulation",
    fallbackReason:"fixture fallback reason",metrics:{width_um:123.5,depth_um:45.25,length_um:201},material:{name:input.material,quality:"estimated",source:"Synthetic fixture source"},
    analyticalComparison:{},assumptions:["Assumption <b>one</b> verbatim","Assumption two"],regime:"r",mainRisk:"m",recommendation:"x",riskScope:"s",
    provenance:{createdAt:CREATED,inputHash:"i".repeat(64),implementationHash:"h".repeat(64),implementationFingerprintSchema:"fp-schema-fixture",solverBinaryHash:null},
    energyBalance:{input_J:1,losses_J:.5,stored_J:.5,relativeError:.0123},
  };
  return {id:"a".repeat(32),status:"completed",progress:1,log:"",error:null,result};
}
const gate = (id: string, status: string, extra: object = {}) => ({id,status,measured:1.5,required:2,unit:"-",note:`note for ${id}`,...extra});
const buildJob = {
  success:true,engine:"fixture",modelId:"model-fixture",solverRevision:"rev-fixture",materialPropertyRevision:"mat-rev-fixture",materialPropertySha256:"m".repeat(64),
  buildJobIdentity:{schemaVersion:1,alloyId:"x",modelId:"model-fixture",solverRevision:"rev-fixture",materialPropertySchemaVersion:1,materialPropertyRevision:"mat-rev-fixture",materialPropertySha256:"m".repeat(64),sha256:"b".repeat(64)},
  assumptions:["Build assumption alpha","Build assumption beta"],alloyId:"x",computeTimeMs:1,thermal:{},slicer:{},
  verdict:{verdict:"risky",headline:"Fixture headline",verdictReason:"Fixture verdict reason",reasons:["reason-first","reason-second","reason-third"],lofGeometry:{widthOverHatch:1,depthOverLayer:1},literatureWindow:{inside:true,alloyId:"x",box:{powerMin_W:1,powerMax_W:2,speedMin_mm_s:1,speedMax_mm_s:2}},
    gates:[gate("gate-block","fail"),gate("gate-risk","warn"),gate("gate-adv","advisory"),gate("gate-na","unavailable",{measured:null,required:null,reason:"geometry unresolved"}),gate("gate-ok","pass")],
    blockingGates:["gate-block"],riskGates:["gate-risk"],advisoryGates:["gate-adv"],unavailableGates:["gate-na"],advisories:["advisory line"],ballingScreened:false,extentStatus:"computed",extentNote:null},
} as unknown as PythonLpbfBuildJobResult;

function reportWith(opts: {job?: boolean; stale?: boolean; ctx?: Partial<LpbfBuildContext>; engineering?: Partial<LpbfEngineeringState>} = {}) {
  const spec = specimen();
  const engineering: LpbfEngineeringState = {...baseEngineering(),...opts.engineering};
  if (opts.job) {
    const job = completedJob();
    engineering.job = job; engineering.submittedInput = job.result!.settings;
    engineering.resultSignature = engineeringSignature(sharedSimulationInput(spec),engineering,spec.lpbf.scanStrategy);
  }
  const effective = opts.stale ? {...spec,lpbf:{...spec.lpbf,laserPower_W:spec.lpbf.laserPower_W+25}} : spec;
  return createLpbfQualificationReport(effective,context(opts.ctx),engineering,buildJob,[]);
}
const build = (report: ReturnType<typeof reportWith>, job: PythonLpbfBuildJobResult | null = buildJob, hash: string | null = "f".repeat(64)) =>
  buildLpbfRunReportHtml(report,{buildJob:job},{createdAt:CREATED,dossierSha256:hash});
const dataBlock = (html: string) => /<script type="application\/json" id="dossier-data">([\s\S]*?)<\/script>/.exec(html)![1];

test("same inputs and createdAt give byte-identical HTML", () => {
  const report = reportWith({job:true});
  assert.equal(build(report),build(report));
  assert.equal(build(report,null),build(report,null));
});

test("hostile text is escaped and the data block cannot be broken out of", () => {
  const evil = "<script>alert(1)</script>";
  const report = reportWith({job:true,ctx:{buildId:evil,notes:`</script><img src=x onerror=alert(2)> ${evil}`},engineering:{measurements:evil,source:"</script>"}});
  const html = build(report);
  assert.equal((html.match(/<script/gi) ?? []).length,1,"only the inert data block is a script element");
  assert.equal((html.match(/<\/script>/gi) ?? []).length,1);
  assert.ok(!html.includes(evil));
  assert.ok(!html.includes("<img"));
  assert.ok(html.includes("&lt;script&gt;alert(1)&lt;/script&gt;"));
  const block = dataBlock(html);
  assert.ok(!block.includes("<"));
  const parsed = JSON.parse(block);
  assert.equal(parsed.buildContext.buildId,evil);
  assert.equal(parsed.buildContext.notes,`</script><img src=x onerror=alert(2)> ${evil}`);
  assert.match(html,/<script type="application\/json" id="dossier-data">/);
});

test("no job: no thermal results and no W/D/L numbers", () => {
  const html = build(reportWith({job:false}));
  assert.match(html,/No completed thermal simulation/);
  assert.ok(!/Width \(W\)|Depth \(D\)|Length \(L\)/.test(html));
  assert.ok(!html.includes("123.5") && !html.includes("45.25"));
  assert.match(html,/Not available - no completed thermal simulation is attached/);
  assert.match(html,/Not recorded/);
});

test("with a job the W/D/L come from the result and a matching run is not stale", () => {
  const html = build(reportWith({job:true}));
  for (const value of ["123.5","45.25","201"]) assert.ok(html.includes(`<td>${value}</td>`),value);
  assert.ok(!html.includes('class="badge"'));
  assert.match(html,/fixture fallback reason/);
  assert.match(html,/Not available - no solver binary was recorded for this backend/);
  assert.match(html,/Not available - not reported by the worker for this run/);
  assert.ok(html.includes("b".repeat(64)) && html.includes("fp-schema-fixture") && html.includes("rev-fixture"));
});

test("a stale run shows the Stale badge", () => {
  const report = reportWith({job:true,stale:true});
  assert.equal(report.resultMatchesCurrentInputs,false);
  const html = build(report);
  assert.match(html,/<span class="badge">Stale<\/span>/);
  assert.match(html,/<td>Differs<\/td>/);
  assert.ok(!html.includes('role="status">Stale'),"static badges are not live regions");
  assert.match(html,/staleness can also come from solver settings or scan strategy/);
  assert.match(html,/describes the current inputs, not the executed run/);
});

test("an alias specimen name compares against the canonical executed material", () => {
  const spec = specimen();
  const store = useMaterialSpecimenStore.getState();
  const original = store.activeSpecimen;
  try {
    useMaterialSpecimenStore.setState({activeSpecimen:{...spec,name:"IN718"}});
    const report = reportWith({job:true});
    assert.equal(report.resultMatchesCurrentInputs,true);
    const html = build(report);
    assert.match(html,/<th scope="row">Material<\/th><td>Inconel 718<\/td><td>Inconel 718<\/td><td>Same<\/td>/);
    assert.ok(!html.includes('class="badge"'));
  } finally {
    useMaterialSpecimenStore.setState({activeSpecimen:original});
  }
});

test("extent status is labelled as build-job geometry, in the build-job section", () => {
  const html = build(reportWith({job:true}));
  assert.ok(!html.includes("<dt>Extent status</dt>"));
  const resultsPart = html.slice(html.indexOf('id="results"'),html.indexOf('id="build-job"'));
  assert.ok(!/extent/i.test(resultsPart));
  const buildPart = html.slice(html.indexOf('id="build-job"'),html.indexOf('id="measurements"'));
  assert.match(buildPart,/<dt>Build-job melt-pool extent status<\/dt><dd>computed<\/dd>/);
  assert.match(buildPart,/<dt>Build-job extent note<\/dt>/);
  assert.match(buildPart,/not the transient thermal W\/D\/L/);
});

test("verdict reasons keep their order and every gate id appears", () => {
  const html = build(reportWith({job:true}));
  const order = ["reason-first","reason-second","reason-third"].map(reason => html.indexOf(`<li>${reason}</li>`));
  assert.ok(order.every(index => index > 0));
  assert.deepEqual([...order].sort((a,b) => a-b),order);
  for (const id of ["gate-block","gate-risk","gate-adv","gate-na","gate-ok"]) assert.ok(html.includes(`<td>${id}</td>`),id);
  assert.match(html,/Fixture headline/);
  assert.match(html,/Fixture verdict reason/);
  assert.match(html,/not balling-cleared/);
  assert.match(html,/<li>advisory line<\/li>/);
  assert.match(html,/<li>Build assumption alpha<\/li><li>Build assumption beta<\/li>/);
  assert.match(html,/Assumption &lt;b&gt;one&lt;\/b&gt; verbatim/);
});

test("no build job prints the no-screening statement and never a verdict", () => {
  const spec = specimen();
  const report = createLpbfQualificationReport(spec,context(),baseEngineering(),null,[]);
  const html = build(report,null);
  assert.match(html,/No build-job screening for the current inputs/);
  assert.ok(!html.replace(/<script[\s\S]*?<\/script>/g,"").includes("gate-block"));
});

test("visible verdict follows the hashed dossier, not a divergent extras job", () => {
  const html = build(reportWith({job:true}),null);
  assert.match(html,/Fixture headline/);
  assert.match(html,/<li>Build assumption alpha<\/li>/);
});

test("the evidence label is report.resultType and no promoted label appears", () => {
  for (const withJob of [false,true]) {
    const report = reportWith({job:withJob});
    const html = build(report);
    assert.equal(/<span class="evidence-label">([^<]*)<\/span>/.exec(html)![1],report.resultType);
    assert.match(html,/not experimental validation, not a production release or standards certificate/);
    const visible = html.replace(/<script[\s\S]*?<\/script>/g,"").replace(/<style[\s\S]*?<\/style>/g,"");
    assert.ok(!/\b(Validated|Qualified|Certified|Production ready)\b/.test(visible),"no promoted label in visible text");
  }
  assert.equal(reportWith({job:true}).resultType,"Screening only");
});

test("the embedded digest equals the node:crypto sha256 of the embedded JSON", async () => {
  const report = reportWith({job:true});
  const json = serializeLpbfRunReportDossier(report,CREATED);
  const expected = createHash("sha256").update(json,"utf8").digest("hex");
  assert.equal(await sha256Hex(json),expected);
  const html = buildLpbfRunReportHtml(report,{buildJob},{createdAt:CREATED,dossierSha256:expected});
  assert.equal(dataBlock(html),json);
  assert.equal(createHash("sha256").update(dataBlock(html),"utf8").digest("hex"),expected);
  assert.ok(html.includes(`<dd>${expected}</dd>`));
  assert.match(build(report,buildJob,null),/<dd>not computed<\/dd>/);
});

test("the file name is sanitized, else the date", () => {
  assert.equal(runReportFileName("B-17",CREATED),"metalliksa-lpbf-run-report-B-17.html");
  assert.equal(runReportFileName("../../etc/pass wd<>:\"|?*",CREATED),"metalliksa-lpbf-run-report-etc-pass-wd.html");
  assert.equal(runReportFileName("   ",CREATED),"metalliksa-lpbf-run-report-2026-01-02.html");
  assert.equal(runReportFileName("...",CREATED),"metalliksa-lpbf-run-report-2026-01-02.html");
  assert.ok(!/[\\/:*?"<>|]/.test(runReportFileName("a/b\\c",CREATED)));
});

test("the export buttons have accessible names and start enabled", () => {
  const markup = renderToStaticMarkup(<LpbfRunReportExport report={reportWith({job:true})} buildJob={buildJob}/>);
  assert.match(markup,/<button[^>]*aria-label="Download run report \(HTML\)"[^>]*>/);
  assert.match(markup,/<button[^>]*aria-label="Open printable report"[^>]*>/);
  assert.ok(!/disabled=""/.test(markup));
  assert.match(markup,/role="status"/);
});

test("the busy state disables both buttons and shows the status message", () => {
  const markup = renderToStaticMarkup(<RunReportButtons busy={true} message="Computing SHA-256 of the dossier JSON..." onAction={()=>undefined}/>);
  assert.equal((markup.match(/<button[^>]*disabled=""/g) ?? []).length,2);
  assert.match(markup,/<p role="status"[^>]*>Computing SHA-256 of the dossier JSON\.\.\.<\/p>/);
});
