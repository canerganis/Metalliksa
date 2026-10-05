import assert from "node:assert/strict";
import test from "node:test";
import {createLatestRequestGate, settleLatestRequest} from "../src/utils/solidificationRequest";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return {promise, resolve, reject};
}

test("a completion from inputs edited during the request is discarded", async () => {
  const gate = createLatestRequestGate();
  const pending = deferred<string>();
  const visible: string[] = [];
  const errors: unknown[] = [];
  const oldGeneration = gate.begin();
  const oldCompletion = settleLatestRequest(gate, oldGeneration, () => pending.promise, {
    onSuccess: (value) => visible.push(value),
    onError: (error) => errors.push(error),
    onFinally: () => visible.push("finished"),
  });

  gate.invalidate(); // the settings changed while fetch was pending
  pending.resolve("old inputs");
  await oldCompletion;

  assert.deepEqual(visible, []);
  assert.deepEqual(errors, []);
});

test("unmount invalidation discards late success and transport errors", async () => {
  const gate = createLatestRequestGate();
  const success = deferred<string>();
  const failure = deferred<never>();
  const visible: string[] = [];
  const errors: unknown[] = [];
  const callbacks = {
    onSuccess: (value: string) => visible.push(value),
    onError: (error: unknown) => errors.push(error),
    onFinally: () => visible.push("finished"),
  };
  const successCompletion = settleLatestRequest(gate, gate.begin(), () => success.promise, callbacks);
  const failureCompletion = settleLatestRequest(gate, gate.begin(), () => failure.promise, callbacks);

  gate.invalidate(); // component unmounted; its effect cleanup invalidates the same gate
  success.resolve("late success");
  failure.reject(new Error("late transport error"));
  await Promise.all([successCompletion, failureCompletion]);

  assert.deepEqual(visible, []);
  assert.deepEqual(errors, []);
});

test("the current generation applies success, errors and loading completion", async () => {
  const gate = createLatestRequestGate();
  const events: string[] = [];
  await settleLatestRequest(gate, gate.begin(), async () => "current result", {
    onSuccess: (value) => events.push(value),
    onError: () => events.push("error"),
    onFinally: () => events.push("finished"),
  });
  await settleLatestRequest(gate, gate.begin(), async () => { throw new Error("current error"); }, {
    onSuccess: () => events.push("unexpected success"),
    onError: () => events.push("error"),
    onFinally: () => events.push("finished"),
  });
  assert.deepEqual(events, ["current result", "finished", "error", "finished"]);
});
