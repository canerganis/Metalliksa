import { Router, type Request, type Response } from "express";
import { generateGpt6Response } from "../server/openaiService.ts";
import { airgapDenyPayload, isAirgappedFromEnv } from "../server/airgap.ts";
import { APPROVED_SOURCE_HOSTS, collectApprovedSource } from "../server/approvedSourceCollector.ts";
import { isOwnKey } from "../server/security.ts";

export const orchestratorRouter = Router();
const MAX_SOURCE_URL_CHARS = 2048;
const MAX_PLAN_FIELD_CHARS = 4000;
const AIRGAPPED = isAirgappedFromEnv(process.env);

function approvedSourceForUrl(rawUrl: string): keyof typeof APPROVED_SOURCE_HOSTS | null {
  try {
    const hostname = new URL(rawUrl).hostname;
    for (const [sourceId, hosts] of Object.entries(APPROVED_SOURCE_HOSTS)) {
      if (hosts.some((host) => hostname === host || hostname.endsWith(`.${host}`))) return sourceId as keyof typeof APPROVED_SOURCE_HOSTS;
    }
  } catch { /* Ignore malformed model output. */ }
  return null;
}

function findDownloadCandidates(text: string) {
  const urls = text.match(/https:\/\/[^\s<>"')\]]+/gi) || [];
  return [...new Set(urls.map((url) => url.replace(/[.,;:]+$/, "")))].filter((url) => /\.(csv|json|zip|txt|xml)(\?|$)/i.test(url));
}

orchestratorRouter.get("/api/orchestrator/approved-sources", (_req: Request, res: Response) => {
  res.json({ sources: APPROVED_SOURCE_HOSTS, automaticCollection: true, modelTraining: false });
});

orchestratorRouter.post("/api/orchestrator/collect-source", async (req: Request, res: Response) => {
  if (AIRGAPPED) return res.status(503).json({ error: "Source collection is disabled in air-gapped mode." });
  const sourceId = req.body?.sourceId;
  const url = typeof req.body?.url === "string" ? req.body.url.trim() : "";
  if (!isOwnKey(APPROVED_SOURCE_HOSTS, sourceId) || !url || url.length > MAX_SOURCE_URL_CHARS) {
    return res.status(400).json({ error: "An approved sourceId and HTTPS URL are required." });
  }
  try {
    const metadata = await collectApprovedSource(sourceId as keyof typeof APPROVED_SOURCE_HOSTS, url);
    return res.status(201).json({ data: metadata, nextStep: "quality-check" });
  } catch (error: any) {
    console.error("[Orchestrator] Approved source collection failed", error);
    return res.status(422).json({ error: error?.message || "Approved source collection failed." });
  }
});

orchestratorRouter.post("/api/orchestrator/dataset-plan", async (req: Request, res: Response) => {
  if (AIRGAPPED) return res.status(503).json(airgapDenyPayload("AI dataset planning"));
  const objective = typeof req.body?.objective === "string" ? req.body.objective.trim() : "";
  const constraints = typeof req.body?.constraints === "string" ? req.body.constraints.trim() : "";
  const availableData = typeof req.body?.availableData === "string" ? req.body.availableData.trim() : "";
  if (!objective) return res.status(400).json({ error: "Dataset objective is required." });
  if (objective.length > MAX_PLAN_FIELD_CHARS || constraints.length > MAX_PLAN_FIELD_CHARS || availableData.length > MAX_PLAN_FIELD_CHARS) {
    return res.status(400).json({ error: `objective, constraints and availableData must each be at most ${MAX_PLAN_FIELD_CHARS} characters.` });
  }

  try {
    const context = `OBJECTIVE:\n${objective}\n\nCONSTRAINTS:\n${constraints || "Not specified"}\n\nAVAILABLE DATA:\n${availableData || "Not specified"}`;
    const sol = await generateGpt6Response({
      model: "gpt-6-sol",
      input: `${context}\n\nRoute this task across the scientific agents. Decide which approved public sources and data groups are relevant, and list the exact questions Astra and Luna must answer. Do not download anything yourself.`,
      instructions: "You route scientific LPBF dataset planning. Return concise, evidence-aware engineering decisions.",
    });
    const astra = await generateGpt6Response({
      model: "gpt-6-astra",
      input: `${context}\n\nSOL ROUTING:\n${sol.text}\n\nAct as the physics and decision gate. Define the minimum physically meaningful variables, controls, targets, uncertainty fields, and rejection criteria for this dataset. Flag any claims that require NIST or other primary-source evidence.`,
      instructions: "You are the LPBF physics and decision gate. Separate evidence from assumptions.",
    });
    const inventory = await generateGpt6Response({
      model: "gpt-6-luna",
      input: `${context}\n\nSOL ROUTING:\n${sol.text}\n\nASTRA PHYSICS GATE:\n${astra.text}\n\nAct as the fast data inventory agent. We currently have no ready local dataset. Propose candidate public sources first, prioritizing the approved allowlist: NIST AM-Bench, Materials Project, and NOMAD when relevant. These approved sources may be collected automatically without another user prompt; arbitrary internet pages may not. For each source, state the exact dataset/record to seek, direct downloadable URL when known, access method, license/terms check, file types, minimum fields, labels, and immediate data-quality checks. Do not claim that a source was downloaded, and do not invent files or measurements.`,
      instructions: "You are the data inventory worker for a scientific LPBF project. Source-first, provenance-first, concrete and concise. Approved-source collection is allowed; arbitrary scraping is forbidden.",
    });
    const review = await generateGpt6Response({
      model: "gpt-6-astra",
      input: `${context}\n\nASTRA PHYSICS GATE:\n${astra.text}\n\nLUNA INVENTORY:\n${inventory.text}\n\nAct as the independent physics reviewer. Check whether each proposed public source is appropriate and traceable. Reject unnecessary variables, identify missing physical controls, propose leakage-safe train/validation/test splits, and list provenance, version, license, citation, and unit requirements. Mark anything that must be manually verified before download.`,
      instructions: "You are the senior LPBF physics reviewer. Check dimensional meaning, experimental comparability, uncertainty and causal leakage.",
    });
    const synthesis = await generateGpt6Response({
      model: "gpt-6-sol",
      input: `${context}\n\nSOL ROUTING:\n${sol.text}\n\nASTRA DECISION GATE:\n${astra.text}\n\nLUNA PROPOSAL:\n${inventory.text}\n\nASTRA REVIEW:\n${review.text}\n\nSynthesize a human-reviewable dataset plan with these exact sections: Decision, Public source shortlist, Required data groups, Required fields, Labels and targets, Split strategy, Provenance, Quality gates, Upload order, Open questions. Clearly state that the local dataset is empty, distinguish source discovery from actual download, include NIST AM-Bench or explain why it is unsuitable, and do not claim that data exists or was retrieved.`,
      instructions: "You are the dataset planning coordinator. Produce a practical plan; data upload must wait for human approval.",
    });
    const collectedSources: unknown[] = [];
    if (availableData.includes("otomatik") || constraints.includes("otomatik")) {
      for (const candidate of findDownloadCandidates(`${inventory.text}\n${review.text}`).slice(0, 3)) {
        const sourceId = approvedSourceForUrl(candidate);
        if (!sourceId) continue;
        try {
          collectedSources.push(await collectApprovedSource(sourceId, candidate));
        } catch (collectionError: any) {
          console.warn(`[Orchestrator] Candidate source skipped: ${candidate}`, collectionError?.message || collectionError);
        }
      }
    }
    return res.json({
      success: true,
      plan: synthesis.text,
      agents: { dispatcher: sol.modelUsed, physicsLead: astra.modelUsed, inventory: inventory.modelUsed, reviewer: review.modelUsed },
      evidence: { dispatcher: sol.text, physicsGate: astra.text, inventory: inventory.text, review: review.text },
      uploadAllowed: false,
      sourceCollectionAllowed: true,
      collectedSources,
    });
  } catch (error: any) {
    console.error("[Orchestrator] Dataset planning failed", error);
    return res.status(error?.message?.includes("OPENAI_API_KEY") ? 503 : 500).json({ error: error?.message || "Dataset planning failed." });
  }
});
