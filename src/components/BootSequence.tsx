/**
 * Boot screen (Phase 9, DESIGN-9 section 4): a discrete checklist of real start-up checks.
 * The shell mounts underneath and keeps loading; this overlay only reports what each check returned.
 * Esc, the backdrop or the skip button hide it (checks keep running and feed the telemetry strip).
 * After a skip or a finished boot, sessionStorage turns the animation off for reloads in this tab;
 * the checks themselves always run.
 */
import React, { Suspense, lazy, useEffect, useState, useSyncExternalStore } from "react";
import { AccessibleModal } from "./AccessibleModal";
import { FoundryStage } from "./FoundryStage";
import { fetchRuntimeConfig, runtimeConfigProbe } from "./AirgapBanner";
import { pythonComputationService } from "../services/pythonComputationService";
import { MODULES } from "../data/workspaces";
import { getBootController } from "../services/bootSteps";
import { setBootOverlayOpen } from "../utils/bootOverlay";
import {
  BOOT_STATE_TEXT,
  bootAnnouncement,
  bootCountLive,
  bootSummary,
  type BootController,
  type BootStepState,
} from "../utils/bootSequence";
// Styles: src/styles/boot.css, imported once from src/main.tsx.

const BootHero = lazy(() => import("./BootHero"));

/**
 * Opening choreography length on a first animated start in the tab. The checks start at once and their
 * rows and state words are on screen from the first frame; this only keeps the emblem on screen long
 * enough to finish drawing when the checks answer faster than the intro. Never applied with reduced
 * motion, after a skip, or on a reload in the same tab (sessionStorage flag): those close as before.
 */
export const BOOT_INTRO_MS = 2800;
/** Overlay fade-out length (matches --mk-dur-slow in boot.css). */
const BOOT_FADE_MS = 420;
const WORDMARK = "METALLIKSA";
// Layers of the orb (one scan vector every 7 units, bottom to top), serpentine like a stripe scan.
const ORB_ROWS = Array.from({ length: 14 }, (_, i) => 167 - i * 7);

/**
 * Decorative emblem, the brand mark at scale: a world built additively. The globe grows bottom-up from
 * scan vectors under a sweeping beam, meridians cut through the finished layers, the unbuilt cap is a
 * hairline graticule, and a laser from above finishes the current layer. Reticle rings around.
 */
function BootEmblem() {
  return (
    <svg className="mk-boot-emblem" viewBox="0 0 200 200" aria-hidden="true" focusable="false">
      <defs>
        <clipPath id="mk-boot-orb">
          <circle cx="100" cy="100" r="70" />
        </clipPath>
        <clipPath id="mk-boot-built">
          <rect x="20" y="72" width="160" height="110" />
        </clipPath>
        <linearGradient id="mk-boot-ray" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="66">
          <stop offset="0" stopColor="var(--mk-laser)" stopOpacity="0" />
          <stop offset="1" stopColor="var(--mk-laser)" stopOpacity="1" />
        </linearGradient>
      </defs>
      <circle className="e-ring" cx="100" cy="100" r="96" pathLength="100" />
      <circle className="e-ticks" cx="100" cy="100" r="86" />
      <circle className="e-inner" cx="100" cy="100" r="70" pathLength="100" />
      <g className="e-graticule">
        <ellipse cx="100" cy="100" rx="26" ry="70" />
        <ellipse cx="100" cy="100" rx="52" ry="70" />
        <line x1="100" x2="100" y1="30" y2="170" />
      </g>
      <g clipPath="url(#mk-boot-orb)">
        {ORB_ROWS.map((y, i) => (
          <line key={y} className="e-hatch" x1={i & 1 ? 172 : 28} x2={i & 1 ? 28 : 172} y1={y} y2={y} pathLength="100" style={{ "--i": i } as React.CSSProperties} />
        ))}
      </g>
      <g className="e-meridians" clipPath="url(#mk-boot-built)">
        <ellipse cx="100" cy="100" rx="26" ry="70" />
        <ellipse cx="100" cy="100" rx="52" ry="70" />
        <line x1="100" x2="100" y1="30" y2="170" />
      </g>
      <line className="e-current" x1="37" x2="118" y1="69" y2="69" pathLength="100" />
      <line className="e-beam" x1="14" x2="186" y1="167" y2="167" />
      <line className="e-ray" x1="118" x2="118" y1="0" y2="66" stroke="url(#mk-boot-ray)" />
      <circle className="e-spot" cx="118" cy="69" r="3.2" />
      <circle className="e-orbit" cx="100" cy="4" r="2.4" />
    </svg>
  );
}

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
  // Intro hold (see BOOT_INTRO_MS): only on an animated start; reduced motion and repeat loads skip it.
  const [holding, setHolding] = useState(snap.animate);
  useEffect(() => {
    if (!holding) return undefined;
    const timer = window.setTimeout(() => setHolding(false), BOOT_INTRO_MS);
    return () => window.clearTimeout(timer);
  }, [holding]);
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
    // The controller already remembered the finished boot (sessionStorage) before entering "done".
    if (snap.phase !== "done") return undefined;
    if (!snap.animate) {
      setGone(true);
      return undefined;
    }
    if (holding) return undefined;
    setLeaving(true);
    const timer = window.setTimeout(() => setGone(true), BOOT_FADE_MS);
    return () => window.clearTimeout(timer);
  }, [snap.phase, snap.animate, holding]);

  const open = !gone && !snap.dismissed;
  // Shell decisions outside this chunk (the command palette never opens over the boot screen).
  useEffect(() => setBootOverlayOpen(open), [open]);
  // The stage stylesheet travels in its own chunk (kept out of the index CSS); the picture mounts once it
  // has arrived, so it never flashes unstyled. The checklist does not wait for it.
  const [stageReady, setStageReady] = useState(false);
  useEffect(() => {
    let live = true;
    import("../styles/foundryStyles").then(() => live && setStageReady(true), () => undefined);
    return () => { live = false; };
  }, []);
  // Esc (shared escape stack), backdrop click and the button all hide the overlay; checks keep running.
  const skip = () => controller.skip();
  const stopped = snap.phase === "stopped";

  // The announcer is always the same first child (never remounted), outside the overlay, so a live
  // region already exists when the final result is written into it after the overlay closes.
  return (
    <>
    <p className="mk-sr-only" role="status" aria-live="polite">
      {bootAnnouncement(snap, open)}
    </p>
    {open && (
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
        {/* The foundry artwork as a live cinemagraph; the WebGL spark layer joins it on a plain animated start. */}
        {stageReady && <FoundryStage className="mk-boot-art" sparks>
          {webgl && wantsHero && (
            <Suspense fallback={null}>
              <BootHero />
            </Suspense>
          )}
        </FoundryStage>}
        <div className="mk-boot-copy">
        <div className="mk-boot-stage">
          <BootEmblem />
          <div>
            <p className="mk-boot-word" aria-hidden="true">
              {[...WORDMARK].map((letter, i) => <span key={i} style={{ "--i": i } as React.CSSProperties}>{letter}</span>)}
            </p>
            <p className="mk-boot-kicker">Local start-up · research workstation</p>
          </div>
        </div>
        <p className="mk-boot-tagline" aria-hidden="true"><span>A world,</span> <span>built by light.</span></p>
        <div className="mk-boot-head">
          <h2 id="boot-title" className="mk-boot-title">Start-up checks</h2>
          {/* Live while checks run and on a sign-in stop; the final result is spoken by the announcer above. */}
          <p id="boot-count" className="mk-boot-count" role="status" aria-live={bootCountLive(snap.phase)}>
            {bootSummary(snap)}
          </p>
        </div>
        {/* One segment per check, filled when that check has answered (a discrete k/N meter, decorative). */}
        <div className="mk-boot-trace" aria-hidden="true">
          {snap.rows.map((row) => <i key={row.id} data-state={row.state} />)}
        </div>
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
        <div className="mk-boot-actions">
          <button type="button" className="mk-boot-skip" onClick={skip}>
            {stopped ? "Continue without signing in" : "Skip intro"}
          </button>
          <span className="mk-boot-hint">Esc also hides this panel. The checks keep running; the status bar at the end of the page shows their outcome.</span>
        </div>
        </div>
      </div>
    </AccessibleModal>
    )}
    </>
  );
}
