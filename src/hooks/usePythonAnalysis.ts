import { useEffect, useRef, useState } from 'react';
import { requestPythonAnalysis } from '../services/pythonAnalysis';
import { useWorkspaceVisible } from '../components/WorkspaceVisibility';

interface AnalysisState<T> {
  key: string;
  result: T | null;
  error: string | null;
  pending: boolean;
  elapsedMs: number | null;
}

/** Input identity gates rendering before effects run; cleanup rejects late replies.
 * Aborting HTTP does not imply that the Python computation has been cancelled.
 *
 * With `options.debounceMs` the request is also delayed until the input has been stable for that long
 * (pending stays true meanwhile), is not sent while the workspace is hidden, and an already finished
 * identical input is not requested again when the workspace is shown. Without options nothing changes.
 */
export function usePythonAnalysis<T>(url: string, payload: unknown, decode: (data: Record<string, unknown>) => T, options?: { debounceMs?: number }) {
  const debounceMs = options?.debounceMs;
  const gated = debounceMs !== undefined;
  const visible = useWorkspaceVisible();
  const doneKey = useRef<string | null>(null);
  const body = JSON.stringify(payload);
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([url, body, attempt]);
  const [state, setState] = useState<AnalysisState<T> | null>(null);
  useEffect(() => {
    if (gated && (!visible || doneKey.current === key)) return;
    const controller = new AbortController();
    const start = performance.now();
    setState(previous => previous?.key === key && previous.pending ? previous : { key, result: null, error: null, pending: true, elapsedMs: null });
    const send = () => requestPythonAnalysis(url, body, controller.signal).then(decode).then(result => {
      if (!controller.signal.aborted) {
        if (gated) doneKey.current = key;
        setState({ key, result, error: null, pending: false, elapsedMs: Math.round(performance.now() - start) });
      }
    }).catch(error => {
      if (!controller.signal.aborted) setState({ key, result: null, error: error instanceof Error ? error.message : 'Python analysis unavailable.', pending: false, elapsedMs: null });
    });
    const timer = gated && debounceMs > 0 ? setTimeout(send, debounceMs) : null;
    if (timer === null) void send();
    return () => { if (timer !== null) clearTimeout(timer); controller.abort(); };
  }, [url, body, key, decode, gated, debounceMs, visible]);
  const current = state?.key === key ? state : null;
  return {
    result: current?.result ?? null,
    error: current?.error ?? null,
    pending: current?.pending ?? true,
    elapsedMs: current?.elapsedMs ?? null,
    retry: () => setAttempt(value => value + 1),
  };
}
