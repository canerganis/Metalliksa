import { useEffect, useRef } from 'react';
import { useWorkspaceVisible } from '../components/WorkspaceVisibility';

export interface IntervalScheduler {
  set: (cb: () => void, ms: number) => unknown;
  clear: (handle: unknown) => void;
}

const browserScheduler: IntervalScheduler = {
  set: (cb, ms) => setInterval(cb, ms),
  clear: (handle) => clearInterval(handle as ReturnType<typeof setInterval>),
};

/** Start an interval; the returned function clears it. Pure, so it is testable without a DOM. */
export function startInterval(callback: () => void, delayMs: number, scheduler: IntervalScheduler = browserScheduler): () => void {
  const handle = scheduler.set(callback, delayMs);
  return () => scheduler.clear(handle);
}

/**
 * Owns start/stop of one interval. `start` is idempotent while running and `stop` is idempotent while
 * stopped, so StrictMode-style start/stop/start sequences never leak a second timer.
 */
export function createVisibleInterval(callback: () => void, delayMs: number, scheduler: IntervalScheduler = browserScheduler) {
  let stopFn: (() => void) | null = null;
  return {
    start(): void {
      if (!stopFn) stopFn = startInterval(callback, delayMs, scheduler);
    },
    stop(): void {
      stopFn?.();
      stopFn = null;
    },
    get running(): boolean { return stopFn !== null; },
  };
}

/**
 * Runs `callback` every `delayMs` only while the workspace is visible (and `delayMs` is not null).
 * Cleared when hidden, restarted when visible again, and cleaned up on unmount.
 * The latest callback is always used without restarting the interval.
 */
export function useVisibleInterval(callback: () => void, delayMs: number | null): void {
  const visible = useWorkspaceVisible();
  const callbackRef = useRef(callback);
  useEffect(() => { callbackRef.current = callback; });
  useEffect(() => {
    if (!visible || delayMs === null) return;
    const controller = createVisibleInterval(() => callbackRef.current(), delayMs);
    controller.start();
    return () => controller.stop();
  }, [visible, delayMs]);
}
