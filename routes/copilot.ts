import { Router, type Request, type Response } from "express";
import { generateGpt6Response } from "../server/openaiService.ts";
import { airgapDenyPayload, isAirgappedFromEnv } from "../server/airgap.ts";

export const copilotRouter = Router();

// Evaluated once at import time; the server/airgap.ts guards read process.env on every call, so changing AIRGAPPED at run time only affects the guards (restart to refresh this route flag).
const AIRGAPPED = isAirgappedFromEnv(process.env);

const MAX_VISION_PROMPT_CHARS = 4000;
const MAX_IMAGE_CHARS = 14_000_000; // ~10 MB of decoded image data

function denyIfAirgapped(res: Response, service: string): boolean {
  if (!AIRGAPPED) return false;
  res.status(503).json(airgapDenyPayload(service));
  return true;
}

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

