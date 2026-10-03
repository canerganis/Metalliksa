import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { AirgapBanner, fetchRuntimeConfig, isWatchedApiRequest } from "../src/components/AirgapBanner";
import { pythonComputationService } from "../src/services/pythonComputationService";

test("isWatchedApiRequest only matches same-origin /api requests other than runtime-config", () => {
  const origin = "http://app.local:3000";
  assert.equal(isWatchedApiRequest("/api/consult", origin), true);
  assert.equal(isWatchedApiRequest("/API/Consult", origin), true);
  assert.equal(isWatchedApiRequest("http://app.local:3000/api/x", origin), true);
  assert.equal(isWatchedApiRequest(new URL("http://app.local:3000/api/x"), origin), true);
  assert.equal(isWatchedApiRequest("/api/runtime-config", origin), false);
  assert.equal(isWatchedApiRequest("http://evil.example/api/x", origin), false);
  assert.equal(isWatchedApiRequest("http://app.local:4000/api/x", origin), false);
  assert.equal(isWatchedApiRequest("/assets/app.js", origin), false);
});

test("a 401 from /api/runtime-config shows the sign-in banner with a link to /login", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = (async () => new Response("{}", { status: 401 })) as typeof fetch;
  try {
    await fetchRuntimeConfig(true);
  } finally {
    globalThis.fetch = realFetch;
  }
  const html = renderToStaticMarkup(<AirgapBanner />);
  assert.match(html, /role="alert"/);
  assert.match(html, /<a href="\/login"/);
});

test("SCRIPT_EXEC_DISABLED server message is surfaced instead of the generic status error", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = (async () =>
    new Response(JSON.stringify({ code: "SCRIPT_EXEC_DISABLED", error: "Script execution is disabled." }), { status: 403 })) as typeof fetch;
  try {
    await assert.rejects(pythonComputationService.executeBatteryCorrosionUserScript("print(1)"), /Script execution is disabled\./);
    globalThis.fetch = (async () => new Response("oops", { status: 500 })) as typeof fetch;
    await assert.rejects(pythonComputationService.executeBatteryCorrosionUserScript("print(1)"), /HTTP 500/);
  } finally {
    globalThis.fetch = realFetch;
  }
});
