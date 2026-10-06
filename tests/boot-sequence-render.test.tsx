import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { BootSequence, bootController } from "../src/components/BootSequence";
import { TelemetryStrip } from "../src/components/TelemetryStrip";
import { SilentBoundary } from "../src/components/SilentBoundary";
import { subsystemQualifier } from "../src/services/bootSteps";
import { MODULES } from "../src/data/workspaces";

test("first paint of the boot screen: a labelled dialog, a plain list of five waiting checks, a live k/N line, an empty persistent announcer, no percent", () => {
  const html = renderToStaticMarkup(<BootSequence />);
  assert.match(html, /role="dialog"/);
  assert.match(html, /aria-labelledby="boot-title"/);
  assert.equal((html.match(/aria-live=/g) ?? []).length, 2, "overlay k/N line + persistent announcer, nothing else");
  assert.match(html, /<p id="boot-count"[^>]*role="status" aria-live="polite">0\/5 checks finished<\/p>/);
  assert.ok(html.startsWith('<p class="mk-sr-only" role="status" aria-live="polite"></p>'), "announcer exists (empty) before the overlay, outside it");
  assert.match(html, /<ol class="mk-boot-rows" aria-label="Start-up checks">/);
  assert.equal((html.match(/<li class="mk-boot-row" data-state="pending">/g) ?? []).length, 5);
  assert.equal((html.match(/>Waiting</g) ?? []).length, 5, "state word once per row");
  assert.ok(!html.includes("mk-boot-detail"), "no detail before a check answers (no 'Waiting Waiting')");
  for (const label of ["Runtime configuration", "Access", "Air-gap", "Python engine", "Module registry (bundled)"]) assert.ok(html.includes(label), label);
  assert.ok(!html.includes("%"), "no percent progress");
  assert.ok(!/online|OK</.test(html), "nothing is reported before a check has answered");
  assert.match(html, />Skip intro</);
});

test("the lazy telemetry strip sits inside a boundary that renders nothing on a chunk/render error", () => {
  assert.deepEqual(SilentBoundary.getDerivedStateFromError(), { failed: true });
  const boundary = new SilentBoundary({ children: <span>strip</span> });
  assert.equal(renderToStaticMarkup(<>{boundary.render()}</>), "<span>strip</span>");
  boundary.state = { failed: true };
  assert.equal(boundary.render(), null);
  const app = readFileSync(resolve(process.cwd(), "src/App.tsx"), "utf8");
  assert.match(app, /<SilentBoundary><Suspense fallback=\{null\}><TelemetryStrip /);
});

test("the boot screen is an early-started lazy chunk behind an opaque, text-free cover and a silent boundary", () => {
  const app = readFileSync(resolve(process.cwd(), "src/App.tsx"), "utf8");
  assert.doesNotMatch(app, /^import [^;]*\.\/components\/BootSequence['"]/m, "not in the index chunk");
  assert.match(app, /^const bootChunk = import\('\.\/components\/BootSequence'\);$/m, "request starts at module evaluation");
  assert.match(app, /bootChunk\.catch\(/, "no unhandled rejection before render");
  assert.match(app, /<SilentBoundary><Suspense fallback=\{<div className="mk-boot-cover" aria-hidden="true" \/>\}><BootSequence \/><\/Suspense><\/SilentBoundary>/);
  assert.doesNotMatch(app, /^import [^;]*services\/bootSteps['"]/m, "App must not pull the boot steps into the index chunk");
});

test("one subsystem wording everywhere: engine-status modal, boot row and strip all use subsystemQualifier", () => {
  assert.equal(subsystemQualifier({ online: true, status: "online", subsystemStatus: "unverified" }), "unverified (server)");
  const dialog = readFileSync(resolve(process.cwd(), "src/components/EngineStatusDialog.tsx"), "utf8");
  assert.match(dialog, /Subsystems: \{status\?\.online \? subsystemQualifier\(status\) : 'unavailable'\}/);
  assert.ok(!dialog.includes("Subsystem status has not been reported"), "old modal wording removed");
  const strip = renderToStaticMarkup(
    <TelemetryStrip engine={{ online: true, status: "online", pythonVersion: "3.14.5", subsystemStatus: "unverified" }} engineChecking={false} moduleCount={MODULES.length} />,
  );
  assert.match(strip, /<dt>Subsystems<\/dt><dd data-tone="neutral">unverified \(server\)<\/dd>/);
});

test("Esc, backdrop and the button share one skip handler that only hides the overlay", () => {
  const src = readFileSync(resolve(process.cwd(), "src/components/BootSequence.tsx"), "utf8");
  const tag = src.slice(src.indexOf("<AccessibleModal"), src.indexOf(">", src.indexOf("panelClassName")));
  assert.match(tag, /onClose=\{skip\}/, "Esc goes through the shared escape stack to skip");
  assert.match(tag, /\bcloseOnBackdrop\b/, "backdrop click skips");
  assert.match(src, /onClick=\{skip\}/);
  assert.match(src, /const skip = \(\) => controller\.skip\(\);/, "skip never cancels or replaces checks");
});

// Runs after the first-paint test: it hides the page singleton for the rest of this file.
test("after a skip only the persistent announcer remains; checks run to the end and it then carries the final result", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = (async () => {
    throw new TypeError("offline in test");
  }) as typeof fetch;
  const announcer = (text: string) => `<p class="mk-sr-only" role="status" aria-live="polite">${text}</p>`;
  try {
    const controller = bootController();
    const run = controller.start();
    controller.skip();
    assert.equal(renderToStaticMarkup(<BootSequence />), announcer(""), "no overlay, nothing announced mid-run");
    await run;
    const snap = controller.getSnapshot();
    assert.equal(snap.finished, 5);
    assert.deepEqual(snap.rows.map((r) => r.state), ["limited", "unavailable", "unavailable", "unavailable", "ok"]);
    assert.equal(
      renderToStaticMarkup(<BootSequence />),
      announcer(
        "Start-up checks finished 5/5 · needs attention: Runtime configuration limited, Access unavailable, Air-gap unavailable, Python engine unavailable",
      ),
    );
  } finally {
    globalThis.fetch = realFetch;
  }
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
