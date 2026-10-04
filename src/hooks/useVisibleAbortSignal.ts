import { useEffect, useState } from 'react';
import { useWorkspaceVisible } from '../components/WorkspaceVisibility';

/**
 * Tracks one AbortController per visible period. Pure, so it is testable without a DOM.
 * `show()` returns a live signal; `hide()` aborts the current one (cancelling in-flight fetches).
 */
export function createVisibleAbortScope() {
  let controller: AbortController | null = null;
  return {
    show(): AbortSignal {
      if (!controller || controller.signal.aborted) controller = new AbortController();
      return controller.signal;
    },
    hide(): void {
      controller?.abort();
      controller = null;
    },
  };
}

/**
 * Owns the signal lifecycle for the hook effect: `show` publishes a live signal through `onSignal`,
 * `hide` aborts it (and publishes null when `notify` is true; unmount cleanup passes false).
 */
export function createVisibleAbort(onSignal: (signal: AbortSignal | null) => void) {
  const scope = createVisibleAbortScope();
  return {
    show(): void { onSignal(scope.show()); },
    hide(notify = true): void {
      scope.hide();
      if (notify) onSignal(null);
    },
  };
}

/**
 * Returns an AbortSignal that is live only while the workspace is visible. It is aborted when the
 * workspace is hidden or the component unmounts, and replaced by a fresh signal when visible again.
 *
 * Returns null while hidden and until the first effect has run (it is always null during server
 * rendering and the first client render); pass it to fetch({ signal }) and skip when null.
 * Consumers must treat the AbortError raised by abort-on-hide as normal cancellation, not as a failure.
 */
export function useVisibleAbortSignal(): AbortSignal | null {
  const visible = useWorkspaceVisible();
  const [signal, setSignal] = useState<AbortSignal | null>(null);
  useEffect(() => {
    if (!visible) { setSignal(null); return; }
    const controller = createVisibleAbort(setSignal);
    controller.show();
    return () => controller.hide(false);
  }, [visible]);
  return visible ? signal : null;
}
