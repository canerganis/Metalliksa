import assert from "node:assert/strict";
import test from "node:test";
import {
  ConsultationResponseError,
  LatestConsultationRequest,
  parseConsultationResponse,
} from "../src/utils/calphadConsultation.ts";

test("parses the server consultation contract and supported legacy text fields", () => {
  assert.equal(parseConsultationResponse({ response: "  thermodynamic assessment  ", text: "same", answer: "same" }), "thermodynamic assessment");
  assert.equal(parseConsultationResponse({ text: "text-only response" }), "text-only response");
  assert.equal(parseConsultationResponse({ answer: "answer-only response" }), "answer-only response");
  assert.equal(parseConsultationResponse({ reply: "legacy response" }), "legacy response");
});

test("rejects empty, non-text, and malformed consultation responses", () => {
  for (const payload of [null, [], {}, { response: "  " }, { text: 42 }, "not an object"]) {
    assert.throws(() => parseConsultationResponse(payload), ConsultationResponseError);
  }
});

test("only the latest consultation request may publish a result", async () => {
  const requests = new LatestConsultationRequest();
  const visible: string[] = [];
  const first = requests.begin();
  const second = requests.begin();

  const publish = async (request: number, value: string) => {
    await Promise.resolve();
    if (requests.isCurrent(request)) visible.push(value);
  };

  await Promise.all([publish(second, "current inputs"), publish(first, "stale inputs")]);
  assert.deepEqual(visible, ["current inputs"]);

  const beforeEdit = requests.begin();
  requests.invalidate();
  await publish(beforeEdit, "edited inputs stale response");
  assert.deepEqual(visible, ["current inputs"]);
});
