import { useEffect } from 'react';
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
 * Runs `callback` every animation frame only while the workspace is visible (and `enabled`).
 * The loop is cancelled when hidden, restarted when visible again, and cleaned up on unmount.
 */
export function useVisibleAnimationFrame(callback: () => void, enabled = true): void {
  const visible = useWorkspaceVisible();
  useEffect(() => {
    if (!visible || !enabled) return;
    return startFrameLoop(callback);
  }, [visible, enabled, callback]);
}
