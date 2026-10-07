import React, { useEffect, useRef, useState } from "react";
import { Download, ExternalLink } from "lucide-react";
import type { PythonLpbfBuildJobResult } from "../services/pythonComputationService";
import { buildLpbfRunReportHtml, runReportFileName, serializeLpbfRunReportDossier, sha256Hex, type LpbfQualificationReport } from "../utils/lpbfRunReport";

const buttonStyle = "rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-sky-300 disabled:opacity-40";

type Action = "download" | "open";

/** One-click self-contained, printable HTML export of the current run. The qualification JSON export is separate and unchanged. */
export function LpbfRunReportExport({report, buildJob}:{report:LpbfQualificationReport;buildJob:PythonLpbfBuildJobResult|null}) {
  const [busy,setBusy] = useState(false);
  const [message,setMessage] = useState("");
  // URLs awaiting revocation. On unmount they are revoked immediately rather than leaked.
  const pending = useRef<Map<string,ReturnType<typeof setTimeout>>>(new Map());
  const mounted = useRef(true);
  useEffect(()=>{
    mounted.current = true;
    const urls = pending.current;
    return ()=>{
      mounted.current = false;
      urls.forEach((timer,url)=>{clearTimeout(timer);URL.revokeObjectURL(url);});
      urls.clear();
    };
  },[]);

  const run = async (action:Action) => {
    if (busy) return;
    setBusy(true);
    setMessage("Computing SHA-256 of the dossier JSON...");
    try {
      const createdAt = new Date().toISOString();
      const digest = await sha256Hex(serializeLpbfRunReportDossier(report,createdAt));
      const html = buildLpbfRunReportHtml(report,{buildJob},{createdAt,dossierSha256:digest});
      const url = URL.createObjectURL(new Blob([html],{type:"text/html;charset=utf-8"}));
      const link = document.createElement("a");
      link.href = url;
      if (action==="download") link.download = runReportFileName(report.buildContext.buildId,createdAt);
      else {link.target="_blank";link.rel="noopener noreferrer";}
      link.click();
      // The opened tab has its own copy once navigation starts; keep the URL alive long enough to load.
      if (mounted.current) pending.current.set(url,setTimeout(()=>{pending.current.delete(url);URL.revokeObjectURL(url);},action==="download"?1000:60000));
      else URL.revokeObjectURL(url);
      setMessage(`${action==="download"?"Download of the run report was requested":"Printable run report requested in a new tab (allow pop-ups if nothing opened)"}. ${digest?"Dossier SHA-256 is printed in the report.":"Dossier SHA-256 not computed on this platform."}`);
    } catch (error) {
      setMessage(`Run report could not be created: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      if (mounted.current) setBusy(false);
    }
  };

  return <RunReportButtons busy={busy} message={message} onAction={action=>{void run(action);}}/>;
}

/** Presentational part, exported so the busy state can be rendered without a DOM. */
export function RunReportButtons({busy,message,onAction}:{busy:boolean;message:string;onAction:(action:Action)=>void}) {
  return <div className="flex flex-wrap items-center gap-2">
    <button type="button" className={buttonStyle} disabled={busy} aria-label="Download run report (HTML)" onClick={()=>onAction("download")}><Download className="mr-2 inline h-4 w-4" aria-hidden="true"/>Download run report (HTML)</button>
    <button type="button" className={buttonStyle} disabled={busy} aria-label="Open printable report" onClick={()=>onAction("open")}><ExternalLink className="mr-2 inline h-4 w-4" aria-hidden="true"/>Open printable report</button>
    <p role="status" aria-live="polite" className="basis-full text-xs text-slate-400">{message}</p>
  </div>;
}
