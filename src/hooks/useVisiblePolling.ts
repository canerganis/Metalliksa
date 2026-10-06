import { useEffect, useRef } from 'react';
import { useWorkspaceVisible } from '../components/WorkspaceVisibility';

export interface TimeoutScheduler {
  set: (cb: () => void, ms: number) => unknown;
  clear: (handle: unknown) => void;
}

const browserScheduler: TimeoutScheduler = {
  set: (cb, ms) => setTimeout(cb, ms),
  clear: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
};

/**
 * One poll step. Resolve with the delay (ms) before the next step, or `null` to stop polling.
 * `isLive()` turns false once the poller was stopped, so a response that arrives after the module
 * was hidden (or unmounted) can be dropped by the caller.
 */
export type PollStep = (isLive: () => boolean) => Promise<number | null>;

/**
 * Self-rescheduling poll loop with an explicit start/stop. `start` is idempotent while running and
 * `stop` cancels the pending timer and invalidates any in-flight step. Pure, so it is testable
 * without a DOM.
 */
export function createVisiblePoller(step: PollStep, scheduler: TimeoutScheduler = browserScheduler) {
  let running = false;
  let epoch = 0;
  let timer: unknown = null;
  const schedule = (ms: number, owner: number) => {
    timer = scheduler.set(() => { timer = null; void run(owner); }, ms);
  };
  const run = async (owner: number): Promise<void> => {
    let next: number | null = null;
    try { next = await step(() => running && owner === epoch); } catch { next = null; }
    if (!running || owner !== epoch) return;
    if (next !== null) schedule(next, owner);
    else running = false;
  };
  return {
    start(firstDelayMs: number): void {
      if (running) return;
      running = true;
      epoch += 1;
      schedule(firstDelayMs, epoch);
    },
    stop(): void {
      running = false;
      epoch += 1;
      if (timer !== null) { scheduler.clear(timer); timer = null; }
    },
    get running(): boolean { return running; },
  };
}

/**
 * Polls `step` only while the workspace is visible and `enabled`. Hiding cancels the pending timer;
 * becoming visible again polls immediately so a job that finished meanwhile is caught up at once.
 * `key` restarts polling (e.g. job id + status) the way an effect dependency would.
 */
export function useVisiblePolling(step: PollStep, enabled: boolean, key: string, firstDelayMs = 1500): void {
  const visible = useWorkspaceVisible();
  const stepRef = useRef(step);
  useEffect(() => { stepRef.current = step; });
  const pausedRef = useRef(false);
  useEffect(() => {
    if (!enabled) return;
    if (!visible) { pausedRef.current = true; return; }
    const delay = pausedRef.current ? 0 : firstDelayMs;
    pausedRef.current = false;
    const poller = createVisiblePoller((isLive) => stepRef.current(isLive));
    poller.start(delay);
    return () => poller.stop();
  }, [visible, enabled, key, firstDelayMs]);
}
