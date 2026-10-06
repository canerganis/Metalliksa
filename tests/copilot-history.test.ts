import assert from "node:assert/strict";
import test from "node:test";
import { buildApiHistory } from "../src/utils/copilotHistory";

test("copilot history excludes the canned welcome, reset notice and client error bubbles", () => {
  const history = buildApiHistory([
    { id: "welcome-1", role: "assistant", content: "Hello, AWS D1.1" },
    { id: "user-1", role: "user", content: "What is Ms?" },
    { id: "assistant-2", role: "assistant", content: "Ms is ..." },
    { id: "error-3", role: "assistant", content: "Consultation error: boom" },
    { id: "welcome-reset", role: "assistant", content: "Chat history cleared" },
    { id: "user-4", role: "user", content: "again" },
  ]);
  assert.deepEqual(history, [
    { role: "user", content: "What is Ms?" },
    { role: "assistant", content: "Ms is ..." },
    { role: "user", content: "again" },
  ]);
});
