import { useEffect, useLayoutEffect, useRef, useState } from 'react';

const useClientLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

/** One current input/attempt owns all replies, including follow-up calculations.
 * HTTP abort only discards transport results; it does not cancel Python work.
 */
export function useInputBoundTask<T>(key: string) {
  const active = useRef<AbortController | null>(null);
  const currentKey = useRef(key);
  const [state, setState] = useState<{
    key: string; data: T | null; error: string | null; pending: string | null;
  } | null>(null);

  useClientLayoutEffect(() => {
    currentKey.current = key;
    setState(null);
    return () => {
      active.current?.abort();
      active.current = null;
    };
  }, [key]);

  const begin = (kind: string) => {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    const isCurrent = () => active.current === controller
      && !controller.signal.aborted && currentKey.current === key;
    setState({ key, data: null, error: null, pending: kind });
    return {
      signal: controller.signal,
      isCurrent,
      publish: (data: T) => {
        if (isCurrent()) setState({ key, data, error: null, pending: kind });
      },
      fail: (error: unknown) => {
        if (isCurrent()) setState({ key, data: null,
          error: error instanceof Error ? error.message : 'Calculation unavailable.', pending: null });
      },
      finish: () => {
        if (isCurrent()) setState(previous => previous ? { ...previous, pending: null } : null);
      },
    };
  };
  const current = state?.key === key ? state : null;
  return { begin, data: current?.data ?? null, error: current?.error ?? null, pending: current?.pending ?? null };
}
