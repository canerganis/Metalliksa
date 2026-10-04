/**
 * Boot screen (Phase 9, DESIGN-9 section 4): a discrete checklist of real start-up checks.
 * The shell mounts underneath and keeps loading; this overlay only reports what each check returned.
 * Esc, the backdrop or the skip button hide it (checks keep running and feed the telemetry strip).
 * After a skip or a finished boot, sessionStorage turns the animation off for reloads in this tab;
 * the checks themselves always run.
 */
import React, { Suspense, lazy, useEffect, useState, useSyncExternalStore } from "react";
import { AlertTriangle, CheckCircle2, Circle, Clock, XCircle } from "lucide-react";
import { AccessibleModal } from "./AccessibleModal";
import { fetchRuntimeConfig, runtimeConfigProbe } from "./AirgapBanner";
import { pythonComputationService } from "../services/pythonComputationService";
import { MODULES } from "../data/workspaces";
import { getBootController, writeSkipFlag } from "../services/bootSteps";
import type { BootController, BootStepState } from "../utils/bootSequence";
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

export const BOOT_STATE_TEXT: Record<BootStepState, string> = {
  pending: "Waiting",
  running: "Checking",
  ok: "OK",
  limited: "Limited",
  unavailable: "Unavailable",
  "timed-out": "Timed out",
  blocked: "Blocked",
  "not-run": "Not run",
};

const ICONS: Partial<Record<BootStepState, typeof Circle>> = {
  ok: CheckCircle2,
  limited: AlertTriangle,
  unavailable: XCircle,
  "timed-out": Clock,
  blocked: XCircle,
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
  const [webgl] = useState(() => snap.animate && webglAvailable());

  useEffect(() => {
    void controller.start();
  }, [controller]);

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
  const configChecked = !["pending", "running"].includes(snap.rows[0]?.state ?? "pending");
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
        <p id="boot-count" className="mk-boot-count">
          {snap.finished}/{snap.total} checks finished{stopped ? " · stopped" : ""}
        </p>
        <div className="mk-boot-trace" aria-hidden="true" />
        <div className="mk-boot-rows">
          {snap.rows.map((row) => {
            const Icon = ICONS[row.state] ?? Circle;
            return (
              <div key={row.id} role="status" className="mk-boot-row" data-state={row.state}>
                <Icon className="mk-boot-icon" aria-hidden="true" />
                <span className="mk-boot-label">{row.label}</span>
                <span className="mk-boot-state">{BOOT_STATE_TEXT[row.state]}</span>
                <span className="mk-boot-detail">{row.detail}</span>
              </div>
            );
          })}
        </div>
        {stopped && (
          <p className="mk-boot-stop">
            Sign-in required: <a href="/login">open the sign-in page</a>, or use the one-time login link printed in the server console.
          </p>
        )}
        {webgl && configChecked && !leaving && (
          <Suspense fallback={null}>
            <BootHero />
          </Suspense>
        )}
        <div className="mk-boot-actions">
          <button type="button" className="mk-boot-skip" onClick={skip}>
            {stopped ? "Continue without signing in" : "Skip intro"}
          </button>
          <span className="mk-boot-hint">Esc also skips. Checks keep running; results stay in the status bar.</span>
        </div>
      </div>
    </AccessibleModal>
  );
}
