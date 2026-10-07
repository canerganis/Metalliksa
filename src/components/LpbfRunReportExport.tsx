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
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(()=>()=>{timers.current.forEach(clearTimeout);},[]);

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
      timers.current.push(setTimeout(()=>URL.revokeObjectURL(url),action==="download"?1000:60000));
      setMessage(`${action==="download"?"Run report downloaded":"Run report opened in a new tab"}. ${digest?"Dossier SHA-256 is printed in the report.":"Dossier SHA-256 not computed on this platform."}`);
    } catch (error) {
      setMessage(`Run report could not be created: ${error instanceof Error ? error.message : "unknown error"}`);
    } finally {
      setBusy(false);
    }
  };

  return <div className="flex flex-wrap items-center gap-2">
    <button type="button" className={buttonStyle} disabled={busy} aria-label="Download run report (HTML)" onClick={()=>{void run("download");}}><Download className="mr-2 inline h-4 w-4" aria-hidden="true"/>Download run report (HTML)</button>
    <button type="button" className={buttonStyle} disabled={busy} aria-label="Open printable report" onClick={()=>{void run("open");}}><ExternalLink className="mr-2 inline h-4 w-4" aria-hidden="true"/>Open printable report</button>
    <p role="status" aria-live="polite" className="basis-full text-xs text-slate-400">{message}</p>
  </div>;
}
