import { assertNotAirgapped } from "./airgap";

export type Gpt6Model = "gpt-6-astra" | "gpt-6-sol" | "gpt-6-luna";

export interface Gpt6ChatMessage { role: "user" | "assistant"; content: string }

type Gpt6Input = string | { messages: Gpt6ChatMessage[] } | {
  imageBase64: string;
  mimeType: "image/jpeg" | "image/png" | "image/webp" | "image/gif";
  prompt: string;
};

export interface Gpt6Request {
  model: Gpt6Model;
  input: Gpt6Input;
  instructions: string;
  timeoutMs?: number;
}

function responseInput(input: Gpt6Input) {
  if (typeof input === "string") return input;
  if ("messages" in input) return input.messages.map(({ role, content }) => ({ role, content }));
  const image = input.imageBase64.replace(/^data:image\/[a-z]+;base64,/, "");
  return [{
    role: "user",
    content: [
      { type: "input_text", text: input.prompt },
      { type: "input_image", image_url: `data:${input.mimeType};base64,${image}`, detail: "auto" },
    ],
  }];
}

export async function generateGpt6Response(
  request: Gpt6Request,
  fetchImpl: typeof fetch = fetch,
): Promise<{ text: string; modelUsed: Gpt6Model }> {
  assertNotAirgapped("GPT-6 AI (copilot / micrograph vision)");
  const apiKey = process.env.OPENAI_API_KEY?.trim();
  if (!apiKey) throw new Error("OPENAI_API_KEY is not configured in the environment.");

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), request.timeoutMs ?? 60_000);
  try {
    const response = await fetchImpl("https://api.openai.com/v1/responses", {
      method: "POST",
      signal: controller.signal,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({
        model: request.model,
        instructions: request.instructions,
        input: responseInput(request.input),
        reasoning: { effort: request.model === "gpt-6-luna" ? "low" : "medium" },
        store: false,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload?.error?.message || `OpenAI API HTTP ${response.status}`);
    if (payload?.status && payload.status !== "completed") {
      throw new Error(`OpenAI response ${payload.status}`);
    }
    const text = payload?.output
      ?.flatMap((item: any) => item.type === "message" ? item.content ?? [] : [])
      .filter((item: any) => item.type === "output_text" && typeof item.text === "string")
      .map((item: any) => item.text)
      .join("\n")
      .trim();
    if (!text) throw new Error("OpenAI returned an empty response.");
    return { text, modelUsed: request.model };
  } finally {
    clearTimeout(timer);
  }
}
