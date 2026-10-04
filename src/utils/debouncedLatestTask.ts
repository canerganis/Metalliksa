/**
 * Debounced "latest input wins" task controller (pure, no React/DOM).
 *
 * - schedule(signature): runs `run` after `delayMs` of quiet. A signature identical to the one that is
 *   already scheduled, running or completed successfully is ignored (no duplicate work).
 * - A different signature clears the pending timer and aborts the superseded in-flight run, so the last
 *   input is always the one computed and a superseded run must not publish (its signal is aborted).
 * - suspend(): hide-time stop. Clears the timer and aborts any unfinished run but keeps a completed result.
 * - runNow(signature): explicit user run; flushes the debounce and re-runs even if already completed.
 *
 * `run` resolves true when its result was published for that signature (it is then remembered as done).
 */
export interface DebouncedLatestTask {
  schedule(signature: string): void;
  runNow(signature: string): void;
  suspend(): void;
  cancel(): void;
}

export function createDebouncedLatestTask(options: {
  /** Read at each schedule so a changed delay takes effect. */
  delayMs: number | (() => number);
  run: (signature: string, signal: AbortSignal) => Promise<boolean | void>;
}): DebouncedLatestTask {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let controller: AbortController | null = null;
  let activeSignature: string | null = null; // scheduled or running
  let doneSignature: string | null = null;

  const stopUnfinished = () => {
    if (timer !== null) { clearTimeout(timer); timer = null; }
    controller?.abort();
    controller = null;
    activeSignature = null;
  };

  const start = (signature: string) => {
    timer = null;
    const own = new AbortController();
    controller = own;
    activeSignature = signature;
    options.run(signature, own.signal).then(
      published => {
        if (controller === own && !own.signal.aborted) {
          controller = null;
          activeSignature = null;
          doneSignature = published === false ? null : signature;
        }
      },
      () => {
        if (controller === own) { controller = null; activeSignature = null; }
      },
    );
  };

  return {
    schedule(signature) {
      if (signature === activeSignature || signature === doneSignature) return;
      stopUnfinished();
      doneSignature = null;
      activeSignature = signature;
      timer = setTimeout(() => start(signature), typeof options.delayMs === "function" ? options.delayMs() : options.delayMs);
    },
    runNow(signature) {
      stopUnfinished();
      doneSignature = null;
      start(signature);
    },
    suspend() {
      stopUnfinished();
    },
    cancel() {
      stopUnfinished();
      doneSignature = null;
    },
  };
}
