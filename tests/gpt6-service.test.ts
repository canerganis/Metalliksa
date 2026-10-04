import assert from "node:assert/strict";
import { test } from "node:test";
import { generateGpt6Response } from "../server/openaiService.ts";
import { copilotRouter } from "../routes/copilot.ts";

function withApiKey(t: any) {
  const previous = process.env.OPENAI_API_KEY;
  process.env.OPENAI_API_KEY = "test-key";
  t.after(() => {
    if (previous === undefined) delete process.env.OPENAI_API_KEY;
    else process.env.OPENAI_API_KEY = previous;
  });
}

function completed(text: string) {
  return new Response(JSON.stringify({
    status: "completed",
    output: [
      { type: "reasoning", summary: [] },
      { type: "message", content: [{ type: "output_text", text }] },
    ],
  }), { status: 200 });
}

test("GPT-6 Sol sends a Responses request with supported reasoning parameters", async t => {
  withApiKey(t);
  let url = "";
  let body: any;
  const mockFetch = async (input: any, init: any) => {
    url = input;
    body = JSON.parse(init.body);
    assert.equal(init.headers.Authorization, "Bearer test-key");
    return completed("grounded result");
  };
  const result = await generateGpt6Response({
    model: "gpt-6-sol", input: "question", instructions: "science assistant",
  }, mockFetch as typeof fetch);
  assert.equal(url, "https://api.openai.com/v1/responses");
  assert.deepEqual(result, { text: "grounded result", modelUsed: "gpt-6-sol" });
  assert.deepEqual(body, {
    model: "gpt-6-sol", instructions: "science assistant", input: "question",
    reasoning: { effort: "medium" }, store: false,
  });
});

test("GPT-6 Astra sends a micrograph as an image input", async t => {
  withApiKey(t);
  let body: any;
  const mockFetch = async (_input: any, init: any) => {
    body = JSON.parse(init.body);
    return completed("visible pores");
  };
  await generateGpt6Response({
    model: "gpt-6-astra",
    instructions: "Describe visible features",
    input: { imageBase64: "data:image/jpeg;base64,AQID", mimeType: "image/jpeg", prompt: "Inspect" },
  }, mockFetch as typeof fetch);
  assert.deepEqual(body.input, [{ role: "user", content: [
    { type: "input_text", text: "Inspect" },
    { type: "input_image", image_url: "data:image/jpeg;base64,AQID", detail: "auto" },
  ] }]);
  assert.equal(body.reasoning.effort, "medium");
});

test("GPT-6 Luna uses low reasoning and incomplete output fails", async t => {
  withApiKey(t);
  let effort = "";
  const mockFetch = async (_input: any, init: any) => {
    effort = JSON.parse(init.body).reasoning.effort;
    return new Response(JSON.stringify({ status: "incomplete", output: [] }), { status: 200 });
  };
  await assert.rejects(generateGpt6Response({
    model: "gpt-6-luna", input: "inventory", instructions: "Inventory sources",
  }, mockFetch as typeof fetch), /incomplete/);
  assert.equal(effort, "low");
});

test("missing OpenAI key fails before any API call", async t => {
  const previous = process.env.OPENAI_API_KEY;
  delete process.env.OPENAI_API_KEY;
  t.after(() => {
    if (previous !== undefined) process.env.OPENAI_API_KEY = previous;
  });
  let called = false;
  await assert.rejects(generateGpt6Response({
    model: "gpt-6-sol", input: "question", instructions: "scientist",
  }, (async () => { called = true; return completed("unexpected"); }) as typeof fetch), /OPENAI_API_KEY/);
  assert.equal(called, false);
});

function postHandler(router: any, path: string) {
  const route = router.stack.find((layer: any) =>
    layer.route?.methods?.post && [layer.route.path].flat().includes(path));
  assert.ok(route, `Missing route ${path}`);
  return route.route.stack[0].handle;
}

function responseRecorder() {
  return {
    statusCode: 200,
    body: null as any,
    status(code: number) { this.statusCode = code; return this; },
    json(body: any) { this.body = body; return this; },
  };
}

test("consultation route returns GPT-6 Sol text using its existing response contract", async t => {
  withApiKey(t);
  const previousFetch = globalThis.fetch;
  let model = "";
  globalThis.fetch = (async (_input: any, init: any) => {
    model = JSON.parse(init.body).model;
    return completed("Evidence-aware answer");
  }) as typeof fetch;
  t.after(() => { globalThis.fetch = previousFetch; });
  const res = responseRecorder();
  await postHandler(copilotRouter, "/api/consult")({ body: { prompt: "Inspect alloy" } }, res);
  assert.equal(model, "gpt-6-sol");
  assert.equal(res.statusCode, 200);
  assert.deepEqual(res.body, {
    response: "Evidence-aware answer", text: "Evidence-aware answer", answer: "Evidence-aware answer",
  });
});

test("micrograph route rejects unsupported SVG before calling GPT-6", async t => {
  withApiKey(t);
  const previousFetch = globalThis.fetch;
  let called = false;
  globalThis.fetch = (async () => { called = true; return completed("unexpected"); }) as typeof fetch;
  t.after(() => { globalThis.fetch = previousFetch; });
  const res = responseRecorder();
  await postHandler(copilotRouter, "/api/metallurgy/diagnose-micrograph")({
    body: { imageBase64: "data:image/svg+xml;base64,PHN2Zz4=", mimeType: "image/svg+xml" },
  }, res);
  assert.equal(res.statusCode, 415);
  assert.equal(called, false);
});
