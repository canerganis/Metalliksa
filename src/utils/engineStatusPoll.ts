/**
 * Bounded re-poll of the Python engine status for the header badge.
 *
 * The daemon finishes starting after the first status check, so one early "unavailable" answer must not stay on
 * screen. The poll retries with a growing delay, stops as soon as the engine reports online, gives up after the
 * last delay, and does not fire while the tab is hidden (it resumes on the next visibility change).
 * It only reads the status route; it never changes what any result claims.
 */
export const ENGINE_POLL_DELAYS_MS: readonly number[] = [2000, 4000, 8000, 16000, 30000];

export interface EnginePollDeps<S extends { online: boolean }> {
  check: () => Promise<S>;
  onStatus: (status: S) => void;
  setTimer: (fn: () => void, ms: number) => unknown;
  clearTimer: (handle: unknown) => void;
  isHidden: () => boolean;
  /** Subscribe to tab visibility changes; returns the unsubscribe function. */
  onVisibilityChange: (cb: () => void) => () => void;
  delaysMs?: readonly number[];
}

/** Starts the poll; the returned function stops it. */
export function startEngineReadyPoll<S extends { online: boolean }>(deps: EnginePollDeps<S>): () => void {
  const delays = deps.delaysMs ?? ENGINE_POLL_DELAYS_MS;
  let stopped = false;
  let handle: unknown = null;
  let waitingForVisible = false;
  let attempt = 0;

  const schedule = () => {
    if (stopped || attempt >= delays.length) return;
    handle = deps.setTimer(fire, delays[attempt]);
  };
  const fire = () => {
    handle = null;
    if (stopped) return;
    if (deps.isHidden()) { waitingForVisible = true; return; }
    attempt += 1;
    deps.check().then(
      (status) => {
        if (stopped) return;
        deps.onStatus(status);
        if (!status.online) schedule();
      },
      () => { if (!stopped) schedule(); },
    );
  };
  const unsubscribe = deps.onVisibilityChange(() => {
    if (stopped || !waitingForVisible || deps.isHidden()) return;
    waitingForVisible = false;
    fire();
  });
  schedule();
  return () => {
    stopped = true;
    if (handle !== null) deps.clearTimer(handle);
    unsubscribe();
  };
}
