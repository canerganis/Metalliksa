import { useCallback, useEffect, useRef } from 'react';
import { createDebouncedLatestTask, type DebouncedLatestTask } from '../utils/debouncedLatestTask';
import { useWorkspaceVisible } from '../components/WorkspaceVisibility';

/**
 * Runs `run(signature, signal)` once the signature has been stable for `delayMs`, only while the
 * workspace is visible. Superseded or hidden runs are aborted (check `signal.aborted` before publishing)
 * and an unchanged signature is never recomputed. `run` must resolve true when it published a result.
 */
export function useDebouncedLatestTask(
  signature: string,
  run: (signature: string, signal: AbortSignal) => Promise<boolean | void>,
  delayMs: number,
) {
  const visible = useWorkspaceVisible();
  const runRef = useRef(run);
  runRef.current = run;
  const delayRef = useRef(delayMs);
  delayRef.current = delayMs;
  const taskRef = useRef<DebouncedLatestTask | null>(null);
  if (!taskRef.current) {
    taskRef.current = createDebouncedLatestTask({ delayMs: () => delayRef.current, run: (sig, signal) => runRef.current(sig, signal) });
  }
  const task = taskRef.current;
  useEffect(() => {
    if (visible) task.schedule(signature); else task.suspend();
  }, [task, signature, visible]);
  useEffect(() => () => task.cancel(), [task]);
  const runNow = useCallback(() => task.runNow(signature), [task, signature]);
  return { runNow };
}
