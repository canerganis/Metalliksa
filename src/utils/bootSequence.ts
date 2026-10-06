/**
 * Boot sequence controller (Phase 9, DESIGN-9 section 4).
 *
 * Pure state machine with no React or DOM dependency. It runs injected startup checks in order,
 * one at a time, and records what each check actually returned. Rules:
 * - Progress is the discrete count of finished checks (k/N); there is no percent and no minimum duration.
 * - A check that does not answer within `timeoutMs` is recorded as "timed-out" and the next check starts.
 * - A check that throws is recorded as "unavailable" with the error text and the next check starts.
 * - A "blocked" outcome (sign-in required) stops the sequence; later checks are recorded as "not-run".
 * - `skip()` only hides the presentation. Checks keep running and their results stay in the snapshot.
 * - Reduced motion or a remembered skip turns animation off; it never skips a check.
 */

export type BootOutcomeState = "ok" | "limited" | "unavailable" | "blocked";
export type BootStepState = "pending" | "running" | "timed-out" | "not-run" | BootOutcomeState;
export type BootPhase = "running" | "complete" | "done" | "stopped";

export interface BootOutcome {
  state: BootOutcomeState;
  detail: string;
}

export interface BootStep {
  id: string;
  label: string;
  run: () => Promise<BootOutcome>;
}

export interface BootRow {
  id: string;
  label: string;
  state: BootStepState;
  detail: string;
}

export interface BootSnapshot {
  rows: readonly BootRow[];
  phase: BootPhase;
  /** Checks that produced a final state (including timed-out). */
  finished: number;
  total: number;
  animate: boolean;
  dismissed: boolean;
}

export interface BootOptions {
  steps: readonly BootStep[];
  timeoutMs?: number;
  exitDelayMs?: number;
  reducedMotion?: boolean;
  skipAnimation?: boolean;
  /** Called on skip() and when the boot finishes, to remember "no animation" for reloads. Never skips a check. */
  remember?: () => void;
}

export interface BootController {
  start(): Promise<void>;
  skip(): void;
  dispose(): void;
  getSnapshot(): BootSnapshot;
  subscribe(listener: () => void): () => void;
}

export const BOOT_STEP_TIMEOUT_MS = 8000;
export const BOOT_EXIT_DELAY_MS = 300;
export const BOOT_SKIP_STORAGE_KEY = "metalliksa.boot.skipAnimation";

const TIMED_OUT = Symbol("timed-out");

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

const ISSUE_STATES: readonly BootStepState[] = ["limited", "unavailable", "timed-out", "blocked"];

/** Text for the single aria-live region: progress k/N, every problem by name, and the final result. */
export function bootSummary(snap: BootSnapshot): string {
  if (snap.phase === "stopped") {
    const row = snap.rows.find((r) => r.state === "blocked");
    return `Start-up stopped at ${row?.label ?? "a check"}: ${row?.detail ?? "blocked"}`;
  }
  const issues = snap.rows.filter((r) => ISSUE_STATES.includes(r.state)).map((r) => `${r.label} ${BOOT_STATE_TEXT[r.state].toLowerCase()}`);
  const done = snap.phase !== "running";
  const head = done ? `Start-up checks finished ${snap.finished}/${snap.total}` : `${snap.finished}/${snap.total} checks finished`;
  return issues.length ? `${head} · needs attention: ${issues.join(", ")}` : done ? `${head} · no problems reported` : head;
}

/**
 * Announcements are split so each is spoken once and never lost with the overlay:
 * - the overlay k/N line is live while checks run and on a sign-in stop (the overlay stays open);
 * - the final result is spoken by a persistent region outside the overlay, filled only after the
 *   overlay has closed (it closes 300 ms after the last check, or earlier on Esc/skip), so it is not
 *   cut off by the unmount and is not hidden behind aria-modal. A sign-in stop after an early skip is
 *   announced by the shell's own role="alert" sign-in banner.
 */
export function bootCountLive(phase: BootPhase): "polite" | "off" {
  return phase === "running" || phase === "stopped" ? "polite" : "off";
}

export function bootAnnouncement(snap: BootSnapshot, overlayOpen: boolean): string {
  return !overlayOpen && (snap.phase === "complete" || snap.phase === "done") ? bootSummary(snap) : "";
}

function errorText(error: unknown): string {
  return error instanceof Error && error.message ? error.message : "check failed";
}

export function createBootController(options: BootOptions): BootController {
  const timeoutMs = options.timeoutMs ?? BOOT_STEP_TIMEOUT_MS;
  const exitDelayMs = options.exitDelayMs ?? BOOT_EXIT_DELAY_MS;
  const listeners = new Set<() => void>();
  let snapshot: BootSnapshot = {
    // Details stay empty until a check answers; the state word alone says "Waiting"/"Checking".
    rows: options.steps.map((s) => ({ id: s.id, label: s.label, state: "pending", detail: "" })),
    phase: "running",
    finished: 0,
    total: options.steps.length,
    animate: !options.reducedMotion && !options.skipAnimation,
    dismissed: false,
  };
  let started: Promise<void> | null = null;
  let exitTimer: ReturnType<typeof setTimeout> | undefined;
  let disposed = false;

  const set = (patch: Partial<BootSnapshot>) => {
    snapshot = { ...snapshot, ...patch };
    listeners.forEach((l) => l());
  };
  const setRows = (from: number, to: number, patch: Pick<BootRow, "state" | "detail">) =>
    set({ rows: snapshot.rows.map((row, i) => (i >= from && i < to ? { ...row, ...patch } : row)) });

  const runWithTimeout = (step: BootStep) =>
    new Promise<BootOutcome | typeof TIMED_OUT>((resolve) => {
      const timer = setTimeout(() => resolve(TIMED_OUT), timeoutMs);
      const settle = (value: BootOutcome | typeof TIMED_OUT) => {
        clearTimeout(timer);
        resolve(value);
      };
      let pending: Promise<BootOutcome>;
      try {
        pending = Promise.resolve(step.run());
      } catch (error) {
        pending = Promise.reject(error);
      }
      pending.then(settle, (error) => settle({ state: "unavailable", detail: errorText(error) }));
    });

  const run = async () => {
    const steps = options.steps;
    for (let i = 0; i < steps.length; i += 1) {
      if (disposed) return;
      setRows(i, i + 1, { state: "running", detail: "" });
      const result = await runWithTimeout(steps[i]);
      if (disposed) return;
      if (result === TIMED_OUT) {
        setRows(i, i + 1, { state: "timed-out", detail: `No answer within ${timeoutMs / 1000} s; continuing` });
      } else {
        setRows(i, i + 1, { state: result.state, detail: result.detail });
      }
      set({ finished: i + 1 });
      if (result !== TIMED_OUT && result.state === "blocked") {
        setRows(i + 1, steps.length, { state: "not-run", detail: "Not checked: start-up stopped" });
        set({ phase: "stopped" });
        return;
      }
    }
    set({ phase: "complete" });
    exitTimer = setTimeout(() => {
      if (disposed) return;
      options.remember?.();
      set({ phase: "done" });
    }, exitDelayMs);
  };

  return {
    start() {
      started ??= run();
      return started;
    },
    skip() {
      options.remember?.();
      if (!snapshot.dismissed) set({ dismissed: true, animate: false });
    },
    dispose() {
      disposed = true;
      if (exitTimer !== undefined) clearTimeout(exitTimer);
      listeners.clear();
    },
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}
