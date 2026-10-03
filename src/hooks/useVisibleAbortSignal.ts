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
 * Returns an AbortSignal that is live only while the workspace is visible. It is aborted when the
 * workspace is hidden or the component unmounts, and replaced by a fresh signal when visible again.
 * Returns null while hidden (and before the first effect); pass it to fetch({ signal }) and skip when null.
 */
export function useVisibleAbortSignal(): AbortSignal | null {
  const visible = useWorkspaceVisible();
  const [signal, setSignal] = useState<AbortSignal | null>(null);
  useEffect(() => {
    if (!visible) { setSignal(null); return; }
    const scope = createVisibleAbortScope();
    setSignal(scope.show());
    return () => { scope.hide(); };
  }, [visible]);
  return visible ? signal : null;
}
