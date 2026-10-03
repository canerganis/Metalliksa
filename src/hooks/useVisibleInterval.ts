import { useEffect } from 'react';
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
 * Runs `callback` every `delayMs` only while the workspace is visible (and `delayMs` is not null).
 * Cleared when hidden, restarted when visible again, and cleaned up on unmount.
 */
export function useVisibleInterval(callback: () => void, delayMs: number | null): void {
  const visible = useWorkspaceVisible();
  useEffect(() => {
    if (!visible || delayMs === null) return;
    return startInterval(callback, delayMs);
  }, [visible, delayMs, callback]);
}
