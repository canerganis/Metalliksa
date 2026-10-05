import assert from "node:assert/strict";
import test from "node:test";
import {
  ConsultationResponseError,
  parseConsultationResponse,
} from "../src/utils/calphadConsultation.ts";
import { CopilotRequestLifecycle, CopyFeedbackLifecycle } from "../src/utils/copilotConsultation.ts";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

test("accepts the consultation route response and rejects missing or empty answer text", () => {
  assert.equal(parseConsultationResponse({ response: "Provider answer", text: "Provider answer", answer: "Provider answer" }), "Provider answer");
  assert.equal(parseConsultationResponse({ text: "Legacy text answer" }), "Legacy text answer");
  assert.throws(() => parseConsultationResponse({ response: "  ", text: "" }), ConsultationResponseError);
  assert.throws(() => parseConsultationResponse({ error: "provider unavailable" }), ConsultationResponseError);
});

test("clear invalidates and aborts pending work; a later reply cannot append stale content", async () => {
  const lifecycle = new CopilotRequestLifecycle();
  const visible: string[] = [];
  const oldResponse = deferred<unknown>();
  const oldRequest = lifecycle.begin();
  const oldCompletion = oldResponse.promise.then((payload) => {
    if (lifecycle.isCurrent(oldRequest)) visible.push(parseConsultationResponse(payload));
  });

  lifecycle.invalidate();
  assert.equal(oldRequest.signal.aborted, true);

  const newResponse = deferred<unknown>();
  const newRequest = lifecycle.begin();
  const newCompletion = newResponse.promise.then((payload) => {
    if (lifecycle.isCurrent(newRequest)) visible.push(parseConsultationResponse(payload));
  });

  newResponse.resolve({ response: "Answer for the new conversation" });
  await newCompletion;
  oldResponse.resolve({ response: "Stale answer from before clear" });
  await oldCompletion;

  assert.deepEqual(visible, ["Answer for the new conversation"]);
});

test("unmount invalidation aborts an outstanding consultation", () => {
  const lifecycle = new CopilotRequestLifecycle();
  const request = lifecycle.begin();

  lifecycle.invalidate();

  assert.equal(request.signal.aborted, true);
  assert.equal(lifecycle.isCurrent(request), false);
});

test("a clipboard completion after clear cannot restore stale feedback", async () => {
  const lifecycle = new CopyFeedbackLifecycle();
  const deferredCopy = deferred<void>();
  let feedback: string | null = null;
  const generation = lifecycle.begin();
  const completion = deferredCopy.promise.then(() => {
    if (lifecycle.isCurrent(generation)) feedback = "copied";
  });

  lifecycle.invalidate(); // clear-history invalidates the UI's same lifecycle
  feedback = null;
  deferredCopy.resolve();
  await completion;

  assert.equal(feedback, null);
});

test("a clipboard completion after unmount cannot publish feedback", async () => {
  const lifecycle = new CopyFeedbackLifecycle();
  const deferredCopy = deferred<void>();
  let feedback: string | null = null;
  const generation = lifecycle.begin();
  const completion = deferredCopy.promise.then(() => {
    if (lifecycle.isCurrent(generation)) feedback = "copied";
  });

  lifecycle.invalidate(); // component cleanup invalidates this lifecycle
  deferredCopy.resolve();
  await completion;

  assert.equal(feedback, null);
});

test("only the newest clipboard operation can publish feedback", async () => {
  const lifecycle = new CopyFeedbackLifecycle();
  const olderCopy = deferred<void>();
  const newerCopy = deferred<void>();
  let feedback: string | null = null;
  const olderGeneration = lifecycle.begin();
  const olderCompletion = olderCopy.promise.then(() => {
    if (lifecycle.isCurrent(olderGeneration)) feedback = "older";
  });
  const newerGeneration = lifecycle.begin();
  const newerCompletion = newerCopy.promise.then(() => {
    if (lifecycle.isCurrent(newerGeneration)) feedback = "newer";
  });

  newerCopy.resolve();
  await newerCompletion;
  olderCopy.resolve();
  await olderCompletion;

  assert.equal(feedback, "newer");
});
