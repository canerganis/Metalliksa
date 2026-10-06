import { Router, type Request, type Response } from "express";
import { generateGpt6Response } from "../server/openaiService.ts";
import { airgapDenyPayload, isAirgappedFromEnv } from "../server/airgap.ts";

export const copilotRouter = Router();

// Evaluated once at import time; the server/airgap.ts guards read process.env on every call, so changing AIRGAPPED at run time only affects the guards (restart to refresh this route flag).
const AIRGAPPED = isAirgappedFromEnv(process.env);

const MAX_PROMPT_CHARS = 8000;
const MAX_SYSTEM_INSTRUCTION_CHARS = 2000;
const MAX_CONTEXT_CHARS = 50000;
const MAX_VISION_PROMPT_CHARS = 4000;
const MAX_HISTORY_MESSAGES = 20;
const MAX_HISTORY_CHARS = 50000;
const MAX_IMAGE_CHARS = 14_000_000; // ~10 MB of decoded image data

// Prior conversation turns sent by the client ({ role, content }[]). A malformed entry is a 400; a long conversation
// keeps only its most recent turns (at most MAX_HISTORY_MESSAGES / MAX_HISTORY_CHARS), dropping the oldest first.
function parseHistory(raw: unknown): { messages: { role: "user" | "assistant"; content: string }[] } | { error: string } {
  if (raw === undefined || raw === null) return { messages: [] };
  if (!Array.isArray(raw)) return { error: "history must be an array of { role, content } messages." };
  const all: { role: "user" | "assistant"; content: string }[] = [];
  for (const item of raw) {
    const role = item?.role;
    const content = item?.content;
    if ((role !== "user" && role !== "assistant") || typeof content !== "string") {
      return { error: "history entries must be { role: 'user' | 'assistant', content: string }." };
    }
    all.push({ role, content });
  }
  const messages = all.slice(-MAX_HISTORY_MESSAGES);
  let chars = messages.reduce((n, m) => n + m.content.length, 0);
  while (messages.length > 0 && chars > MAX_HISTORY_CHARS) chars -= messages.shift()!.content.length;
  return { messages };
}

function denyIfAirgapped(res: Response, service: string): boolean {
  if (!AIRGAPPED) return false;
  res.status(503).json(airgapDenyPayload(service));
  return true;
}

// General Metallurgy Consultation & Copilot Guidance
copilotRouter.post(["/api/metallurgy/consult", "/api/consult"], async (req: Request, res: Response) => {
  if (denyIfAirgapped(res, "GPT-6 AI consultation")) return;
  try {
    const { prompt, message, context, systemInstruction, history } = req.body ?? {};
    const rawPrompt = prompt || message;
    if (rawPrompt !== undefined && (typeof rawPrompt !== "string" || rawPrompt.length > MAX_PROMPT_CHARS)) {
      return res.status(400).json({ error: `prompt must be a string of at most ${MAX_PROMPT_CHARS} characters.` });
    }
    if (systemInstruction !== undefined && systemInstruction !== null && (typeof systemInstruction !== "string" || systemInstruction.length > MAX_SYSTEM_INSTRUCTION_CHARS)) {
      return res.status(400).json({ error: `systemInstruction must be a string of at most ${MAX_SYSTEM_INSTRUCTION_CHARS} characters.` });
    }
    const parsedHistory = parseHistory(history);
    if ("error" in parsedHistory) return res.status(400).json({ error: parsedHistory.error });
    const userPrompt = rawPrompt || "Provide metallurgical analysis and ICME optimization advice.";

    let contextText = "";
    if (context) {
      contextText = typeof context === "string" ? context : (JSON.stringify(context) ?? "");
      if (contextText.length > MAX_CONTEXT_CHARS) {
        return res.status(400).json({ error: `context must be at most ${MAX_CONTEXT_CHARS} characters when serialized.` });
      }
    }

    const fullPrompt = contextText
      ? `Material Context: ${contextText}\n\nQuery: ${userPrompt}`
      : userPrompt;

    const response = await generateGpt6Response({
      model: "gpt-6-sol",
      // Prior turns are forwarded so follow-up questions are answered in context; no history keeps the plain string input.
      input: parsedHistory.messages.length
        ? { messages: [...parsedHistory.messages, { role: "user" as const, content: fullPrompt }] }
        : fullPrompt,
      instructions: systemInstruction || "You are an expert physical metallurgist, CALPHAD thermodynamicist, and additive manufacturing specialist. Provide precise, quantitative, and scientifically rigorous insights. Distinguish calculations and evidence from hypotheses.",
    });

    const text = response.text;
    return res.json({ response: text, text, answer: text });
  } catch (err: any) {
    console.error("[Copilot Error]", err);
    return res.status(err?.message?.includes("OPENAI_API_KEY") ? 503 : 500).json({ error: err.message || "Consultation request failed" });
  }
});

// SEM & Micrograph Vision Diagnostics
copilotRouter.post("/api/metallurgy/diagnose-micrograph", async (req: Request, res: Response) => {
  if (denyIfAirgapped(res, "GPT-6 micrograph vision")) return;
  try {
    const { imageBase64, prompt } = req.body ?? {};
    if (imageBase64 !== undefined && imageBase64 !== null && typeof imageBase64 !== "string") {
      return res.status(400).json({ error: "imageBase64 must be a string." });
    }
    if (typeof imageBase64 === "string" && imageBase64.length > MAX_IMAGE_CHARS) {
      return res.status(413).json({ error: "Micrograph image is too large." });
    }
    if (prompt !== undefined && prompt !== null && (typeof prompt !== "string" || prompt.length > MAX_VISION_PROMPT_CHARS)) {
      return res.status(400).json({ error: `prompt must be a string of at most ${MAX_VISION_PROMPT_CHARS} characters.` });
    }
    // The data-URI mime type wins over the client-supplied mimeType field.
    const mimeType = typeof imageBase64 === "string" && imageBase64.startsWith("data:")
      ? imageBase64.match(/^data:([^;]+);base64,/)?.[1]
      : req.body?.mimeType || "image/jpeg";
    if (imageBase64 && !["image/jpeg", "image/png", "image/webp", "image/gif"].includes(mimeType)) {
      return res.status(415).json({ error: "Upload a JPEG, PNG, WebP, or GIF micrograph for GPT-6 analysis." });
    }
    const response = await generateGpt6Response({
      model: "gpt-6-astra",
      input: imageBase64
        ? { imageBase64, mimeType, prompt: prompt || "Describe visible microstructure features, grain boundaries, and possible defects. State uncertainty and avoid unsupported quantitative claims." }
        : prompt || "Analyze micrograph morphology.",
      instructions: "You are an expert metallographer. Describe only features supported by the image. Do not infer phase identity or quantitative measurements without evidence.",
    });

    return res.json({
      diagnosis: response.text,
    });
  } catch (err: any) {
    return res.status(err?.message?.includes("OPENAI_API_KEY") ? 503 : 500).json({ error: err.message || "Micrograph analysis failed" });
  }
});

