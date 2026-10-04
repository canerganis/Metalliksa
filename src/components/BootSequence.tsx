/**
 * Boot screen (Phase 9, DESIGN-9 section 4): a discrete checklist of real start-up checks.
 * The shell mounts underneath and keeps loading; this overlay only reports what each check returned.
 * Esc, the backdrop or the skip button hide it (checks keep running and feed the telemetry strip).
 * After a skip or a finished boot, sessionStorage turns the animation off for reloads in this tab;
 * the checks themselves always run.
 */
import React, { Suspense, lazy, useEffect, useState, useSyncExternalStore } from "react";
import { AccessibleModal } from "./AccessibleModal";
import { fetchRuntimeConfig, runtimeConfigProbe } from "./AirgapBanner";
import { pythonComputationService } from "../services/pythonComputationService";
import { MODULES } from "../data/workspaces";
import { getBootController, writeSkipFlag } from "../services/bootSteps";
import { BOOT_STATE_TEXT, bootSummary, type BootController, type BootStepState } from "../utils/bootSequence";
// Styles: src/styles/boot.css, imported once from src/main.tsx.

const BootHero = lazy(() => import("./BootHero"));

export function bootController(): BootController {
  return getBootController(() => ({
    loadConfig: () => fetchRuntimeConfig(),
    probe: runtimeConfigProbe,
    engineStatus: () => pythonComputationService.checkEngineStatus(false),
    moduleCount: () => MODULES.length,
  }));
}

export function useBootSnapshot() {
  const controller = bootController();
  return useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
}

// Shape cue next to the state word, so colour is never the only signal (decorative, aria-hidden).
const GLYPHS: Record<BootStepState, string> = {
  pending: "○",
  running: "•",
  ok: "✓",
  limited: "!",
  unavailable: "✕",
  "timed-out": "⧗",
  blocked: "✕",
  "not-run": "–",
};

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    return gl !== null;
  } catch {
    return false;
  }
}

export function BootSequence() {
  const controller = bootController();
  const snap = useBootSnapshot();
  const [leaving, setLeaving] = useState(false);
  const [gone, setGone] = useState(false);
  const [webgl, setWebgl] = useState(false);
  const configChecked = !["pending", "running"].includes(snap.rows[0]?.state ?? "pending");
  // Hero only for a plain start (no deep link) with motion allowed, after the config check.
  const deepLink = typeof window !== "undefined" && window.location.hash.length > 1;
  const wantsHero = snap.animate && configChecked && !snap.dismissed && !leaving && !deepLink;

  useEffect(() => {
    void controller.start();
  }, [controller]);

  useEffect(() => {
    // WebGL is probed only at the moment the hero would mount, never on a static or skipped boot.
    if (wantsHero && !webgl) setWebgl(webglAvailable());
  }, [wantsHero, webgl]);

  useEffect(() => {
    if (snap.phase !== "done") return undefined;
    writeSkipFlag();
    if (!snap.animate) {
      setGone(true);
      return undefined;
    }
    setLeaving(true);
    const timer = window.setTimeout(() => setGone(true), 200);
    return () => window.clearTimeout(timer);
  }, [snap.phase, snap.animate]);

  if (gone || snap.dismissed) return null;

  const skip = () => {
    writeSkipFlag();
    controller.skip();
  };
  const stopped = snap.phase === "stopped";

  return (
    <AccessibleModal
      open
      onClose={skip}
      labelledBy="boot-title"
      describedBy="boot-count"
      closeOnBackdrop
      overlayClassName={`mk-boot-overlay p-4${leaving ? " is-leaving" : ""}`}
      panelClassName="mk-boot-panel"
    >
      <div className="mk-boot" data-animate={String(snap.animate)} data-phase={snap.phase}>
        <p className="mk-boot-kicker">Metalliksa · local start-up</p>
        <h2 id="boot-title" className="mk-boot-title">Start-up checks</h2>
        {/* The single live region: k/N progress, every problem by name, and the final result. */}
        <p id="boot-count" className="mk-boot-count" role="status" aria-live="polite">
          {bootSummary(snap)}
        </p>
        <div className="mk-boot-trace" aria-hidden="true" />
        <ol className="mk-boot-rows" aria-label="Start-up checks">
          {snap.rows.map((row) => (
            <li key={row.id} className="mk-boot-row" data-state={row.state}>
              <span className="mk-boot-icon" aria-hidden="true">{GLYPHS[row.state]}</span>
              <span className="mk-boot-label">{row.label}</span>
              <span className="mk-boot-state">{BOOT_STATE_TEXT[row.state]}</span>
              {row.detail && <span className="mk-boot-detail">{row.detail}</span>}
            </li>
          ))}
        </ol>
        {stopped && (
          <p className="mk-boot-stop">
            Sign-in required: <a href="/login">open the sign-in page</a>, or use the one-time login link printed in the server console.
          </p>
        )}
        {webgl && wantsHero && (
          <Suspense fallback={null}>
            <BootHero />
          </Suspense>
        )}
        <div className="mk-boot-actions">
          <button type="button" className="mk-boot-skip" onClick={skip}>
            {stopped ? "Continue without signing in" : "Skip intro"}
          </button>
          <span className="mk-boot-hint">Esc also hides this panel. The checks keep running; the status bar at the end of the page shows their outcome.</span>
        </div>
      </div>
    </AccessibleModal>
  );
}
