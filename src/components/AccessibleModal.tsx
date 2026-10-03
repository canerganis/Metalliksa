import { useEffect, useRef } from "react";

type EscapeEntry = { current: () => void };

// Open overlays register here in opening order; only the topmost one reacts to Escape,
// so nested dialogs (for example a CNLS import dialog inside the CNLS studio modal) close one at a time.
const escapeStack: EscapeEntry[] = [];
let listenerInstalled = false;

function onKeyDown(event: KeyboardEvent): void {
  if (event.key !== "Escape" || event.defaultPrevented) return;
  const top = escapeStack[escapeStack.length - 1];
  if (!top) return;
  event.preventDefault();
  top.current();
}

/**
 * Closes the topmost open overlay when Escape is pressed.
 * Call it unconditionally at the top of the component (before any early return).
 */
export function useEscapeToClose(active: boolean, onClose: () => void): void {
  const entry = useRef<EscapeEntry>({ current: onClose });
  entry.current.current = onClose;

  useEffect(() => {
    if (!active) return undefined;
    const registered = entry.current;
    escapeStack.push(registered);
    if (!listenerInstalled) {
      window.addEventListener("keydown", onKeyDown);
      listenerInstalled = true;
    }
    return () => {
      const index = escapeStack.lastIndexOf(registered);
      if (index !== -1) escapeStack.splice(index, 1);
      if (escapeStack.length === 0 && listenerInstalled) {
        window.removeEventListener("keydown", onKeyDown);
        listenerInstalled = false;
      }
    };
  }, [active]);
}
