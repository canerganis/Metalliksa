import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { AirgapBanner, fetchRuntimeConfig, installApiUnauthorizedWatcher, isWatchedApiRequest } from "../src/components/AirgapBanner";
import { pythonComputationService } from "../src/services/pythonComputationService";

test("isWatchedApiRequest only matches same-origin /api requests other than runtime-config", () => {
  const origin = "http://app.local:3000";
  assert.equal(isWatchedApiRequest("/api/consult", origin), true);
  assert.equal(isWatchedApiRequest("/API/Consult", origin), true);
  assert.equal(isWatchedApiRequest("http://app.local:3000/api/x", origin), true);
  assert.equal(isWatchedApiRequest(new URL("http://app.local:3000/api/x"), origin), true);
  assert.equal(isWatchedApiRequest(new Request("http://app.local:3000/api/x", { method: "POST" }), origin), true);
  assert.equal(isWatchedApiRequest(new Request("http://evil.example/api/x"), origin), false);
  assert.equal(isWatchedApiRequest(new Request("http://app.local:3000/api/runtime-config"), origin), false);
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

// Keep this test last: the watcher installs once per module and then owns fetchRuntimeConfig's fetch.
test("installApiUnauthorizedWatcher re-checks runtime-config only for same-origin /api 401s, once, without altering responses", async () => {
  const origin = "http://app.local:3000";
  const statuses = new Map<string, number>();
  const calls: string[] = [];
  let gate: Promise<void> = Promise.resolve();
  const stub = (async (input: any) => {
    const raw: string = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    calls.push(raw);
    if (raw.includes("/boom")) throw new TypeError("network down");
    if (raw.endsWith("/api/runtime-config")) {
      await gate;
      return new Response("{}", { status: statuses.get(raw) ?? 200 });
    }
    return new Response("body:" + raw, { status: statuses.get(raw) ?? 200 });
  }) as typeof fetch;
  const g = globalThis as any;
  const hadWindow = "window" in g;
  const prevWindow = g.window;
  g.window = { fetch: stub, location: { origin } };
  const rcCalls = () => calls.filter((c) => c.endsWith("/api/runtime-config")).length;
  const settle = () => new Promise((r) => setTimeout(r, 5));
  try {
    installApiUnauthorizedWatcher();
    const wrapped = g.window.fetch;
    assert.notEqual(wrapped, stub, "fetch is wrapped");
    installApiUnauthorizedWatcher();
    assert.equal(g.window.fetch, wrapped, "a second install does not wrap again");

    // Non-401, cross-origin and non-api requests never re-check.
    statuses.set("/api/ok", 200);
    statuses.set("/api/server-error", 500);
    statuses.set("http://evil.example/api/x", 401);
    statuses.set("/assets/a.js", 401);
    await wrapped("/api/ok");
    await wrapped("/api/server-error");
    await wrapped("http://evil.example/api/x");
    await wrapped("/assets/a.js");
    await settle();
    assert.equal(rcCalls(), 0);

    // A 401 from /api/runtime-config itself never triggers another check.
    statuses.set("/api/runtime-config", 401);
    await wrapped("/api/runtime-config");
    await settle();
    assert.equal(rcCalls(), 1, "only the direct call");
    statuses.delete("/api/runtime-config");

    // A same-origin /api 401 triggers exactly one re-check and returns the response untouched.
    statuses.set("/api/consult", 401);
    const before = rcCalls();
    const res = await wrapped("/api/consult");
    assert.equal(res.status, 401);
    assert.equal(await res.text(), "body:/api/consult", "body is not consumed");
    await settle();
    assert.equal(rcCalls() - before, 1);

    // Concurrent 401s coalesce into a single re-check while one is in flight.
    let release!: () => void;
    gate = new Promise<void>((r) => (release = r));
    const base = rcCalls();
    statuses.set(origin + "/api/consult", 401);
    await Promise.all([wrapped("/api/consult"), wrapped("/api/consult"), wrapped(new Request(origin + "/api/consult"))]);
    await settle();
    assert.equal(rcCalls() - base, 1);
    release();
    await settle();
    // Once settled, a new 401 triggers a new re-check.
    gate = Promise.resolve();
    await wrapped("/api/consult");
    await settle();
    assert.equal(rcCalls() - base, 2);

    // A rejected fetch passes through unchanged and triggers nothing.
    const n = rcCalls();
    await assert.rejects(wrapped("/api/boom"), (e: any) => e instanceof TypeError && e.message === "network down");
    await settle();
    assert.equal(rcCalls(), n);
  } finally {
    if (hadWindow) g.window = prevWindow;
    else delete g.window;
  }
});
