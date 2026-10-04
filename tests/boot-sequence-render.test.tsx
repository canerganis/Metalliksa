import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { BootSequence } from "../src/components/BootSequence";
import { TelemetryStrip } from "../src/components/TelemetryStrip";
import { MODULES } from "../src/data/workspaces";

test("first paint of the boot screen: a labelled dialog with five waiting role=status rows and k/N, no percent", () => {
  const html = renderToStaticMarkup(<BootSequence />);
  assert.match(html, /role="dialog"/);
  assert.match(html, /aria-labelledby="boot-title"/);
  assert.equal((html.match(/role="status"/g) ?? []).length, 5);
  assert.match(html, /0\/5 checks finished/);
  for (const label of ["Runtime configuration", "Access", "Air-gap", "Python engine", "Module registry"]) assert.ok(html.includes(label), label);
  assert.ok(!html.includes("%"), "no percent progress");
  assert.ok(!/online|OK</.test(html), "nothing is reported before a check has answered");
  assert.match(html, />Skip intro</);
});

test("telemetry strip before any source answers: 'checking'/'unavailable', never a placeholder value", () => {
  const html = renderToStaticMarkup(<TelemetryStrip engine={null} engineChecking moduleCount={MODULES.length} />);
  assert.match(html, /<footer class="mk-telemetry" aria-label="System telemetry">/);
  assert.match(html, /<dt>Engine<\/dt><dd data-tone="neutral">checking<\/dd>/);
  assert.match(html, /<dt>Air-gap<\/dt><dd data-tone="neutral">checking<\/dd>/);
  assert.match(html, new RegExp(`<dt>Modules</dt><dd data-tone="neutral">${MODULES.length} registered</dd>`));
  const offline = renderToStaticMarkup(<TelemetryStrip engine={{ online: false, status: "client_fallback" }} engineChecking={false} moduleCount={MODULES.length} />);
  assert.match(offline, /<dt>Engine<\/dt><dd data-tone="fail">unavailable<\/dd>/);
  assert.match(offline, /<dt>Subsystems<\/dt><dd data-tone="fail">unavailable<\/dd>/);
});
