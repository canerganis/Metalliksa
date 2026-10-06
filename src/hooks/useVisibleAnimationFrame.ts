import { useEffect, useRef } from 'react';
import { useWorkspaceVisible } from '../components/WorkspaceVisibility';

export interface FrameScheduler {
  request: (cb: () => void) => number;
  cancel: (id: number) => void;
}

const browserScheduler: FrameScheduler = {
  request: (cb) => requestAnimationFrame(cb),
  cancel: (id) => cancelAnimationFrame(id),
};

/** Start a self-rescheduling frame loop; the returned function cancels it. Pure, so it is testable without a DOM. */
export function startFrameLoop(callback: () => void, scheduler: FrameScheduler = browserScheduler): () => void {
  let id = 0;
  let stopped = false;
  const loop = () => {
    if (stopped) return;
    callback();
    if (stopped) return;
    id = scheduler.request(loop);
  };
  id = scheduler.request(loop);
  return () => { stopped = true; scheduler.cancel(id); };
}

/**
 * Owns start/stop of one frame loop. `start` is idempotent while running and `stop` is idempotent while
 * stopped, so StrictMode-style start/stop/start sequences never leak a second loop.
 */
export function createVisibleLoop(callback: () => void, scheduler: FrameScheduler = browserScheduler) {
  let stopFn: (() => void) | null = null;
  return {
    start(): void {
      if (!stopFn) stopFn = startFrameLoop(callback, scheduler);
    },
    stop(): void {
      stopFn?.();
      stopFn = null;
    },
    get running(): boolean { return stopFn !== null; },
  };
}

/**
 * Runs `callback` every animation frame only while the workspace is visible (and `enabled`).
 * The loop is cancelled when hidden, restarted when visible again, and cleaned up on unmount.
 * The latest callback is always used without restarting the loop.
 */
export function useVisibleAnimationFrame(callback: () => void, enabled = true): void {
  const visible = useWorkspaceVisible();
  const callbackRef = useRef(callback);
  useEffect(() => { callbackRef.current = callback; });
  useEffect(() => {
    if (!visible || !enabled) return;
    const controller = createVisibleLoop(() => callbackRef.current());
    controller.start();
    return () => controller.stop();
  }, [visible, enabled]);
}
