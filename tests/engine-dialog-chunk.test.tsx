import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SilentBoundary } from "../src/components/SilentBoundary";

// Review fix 2: a failed EngineStatusDialog chunk must not leave showStatus stuck with nothing on screen.
const app = readFileSync(resolve(process.cwd(), "src/App.tsx"), "utf8").replace(/\r/g, "");

test("SilentBoundary renders its fallback after a failure (and nothing without one)", () => {
  assert.deepEqual(SilentBoundary.getDerivedStateFromError(), { failed: true });
  const withFallback = new SilentBoundary({ children: <span>dialog</span>, fallback: <p role="alert">failed</p> });
  assert.equal(renderToStaticMarkup(<>{withFallback.render()}</>), "<span>dialog</span>");
  withFallback.state = { failed: true };
  assert.equal(renderToStaticMarkup(<>{withFallback.render()}</>), '<p role="alert">failed</p>');
  const silent = new SilentBoundary({ children: <span>strip</span> });
  silent.state = { failed: true };
  assert.equal(silent.render(), null);
});

test("engine dialog chunk failure: alert with Retry (fresh lazy import) and Close (resets showStatus)", () => {
  assert.match(app, /const loadEngineStatusDialog = \(\) => lazy\(\(\) => import\('\.\/components\/EngineStatusDialog'\)/);
  assert.doesNotMatch(app, /^const EngineStatusDialog = lazy\(/m, "a module-level lazy would cache the rejection forever");
  assert.match(app, /const EngineStatusDialog = useMemo\(loadEngineStatusDialog, \[dialogLoad\]\);/);
  assert.match(app, /const retryDialog = \(\) => setDialogLoad\(n => n \+ 1\);/);
  assert.match(app, /const closeDialog = \(\) => \{ setShowStatus\(false\); retryDialog\(\); \};/);
  const fallback = app.match(/<SilentBoundary key=\{dialogLoad\} fallback=\{(<div role="alert"[\s\S]*?<\/div>)\}>/)?.[1] ?? "";
  assert.match(fallback, /Engine availability details could not be loaded\./);
  assert.match(fallback, /<button onClick=\{retryDialog\}[^>]*>Retry<\/button>/);
  assert.match(fallback, /<button onClick=\{closeDialog\}[^>]*>Close<\/button>/);
  assert.match(fallback, /<button onClick=\{\(\) => window\.location\.reload\(\)\}[^>]*>Reload application<\/button>/, "Chrome keeps a failed module fetch, so a reload is offered too");
  assert.doesNotMatch(fallback, /inset-0/, "a non-modal alert, not a second overlay");
});
