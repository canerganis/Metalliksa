/**
 * Shared overlay accessibility primitives.
 *
 * - `useEscapeToClose(active, onClose)`: hook for overlays that keep their own markup. Only the topmost
 *   registered overlay reacts to Escape (module-level `escapeStack`).
 * - `<AccessibleModal open onClose label | labelledBy>`: dialog wrapper with role="dialog", aria-modal,
 *   focus trap, focus restore and the same overlay classes as the existing modals.
 *
 * Usage:
 *   <AccessibleModal open={open} onClose={close} labelledBy="my-title" closeOnBackdrop lockScroll>
 *     <h2 id="my-title">Title</h2>
 *     ...content...
 *   </AccessibleModal>
 *
 * Pass `panelClassName` / `overlayClassName` to override the default look.
 */
import React, { useEffect, useRef } from "react";

type EscapeEntry = { current: () => void };

// Open overlays register here in opening order; only the topmost one reacts to Escape,
// so nested dialogs (for example a CNLS import dialog inside the CNLS studio modal) close one at a time.
const escapeStack: EscapeEntry[] = [];
let listenerInstalled = false;

/** Registers an overlay on the stack; returns the unregister function. */
export function registerEscapeEntry(entry: EscapeEntry): () => void {
  escapeStack.push(entry);
  if (!listenerInstalled && typeof window !== "undefined") {
    window.addEventListener("keydown", onKeyDown);
    listenerInstalled = true;
  }
  return () => {
    const index = escapeStack.lastIndexOf(entry);
    if (index !== -1) escapeStack.splice(index, 1);
    if (escapeStack.length === 0 && listenerInstalled) {
      window.removeEventListener("keydown", onKeyDown);
      listenerInstalled = false;
    }
  };
}

/** Closes only the topmost overlay. Returns false when the stack is empty. */
export function closeTopmostOverlay(): boolean {
  const top = escapeStack[escapeStack.length - 1];
  if (!top) return false;
  top.current();
  return true;
}

export function escapeStackDepth(): number {
  return escapeStack.length;
}

function onKeyDown(event: KeyboardEvent): void {
  if (event.key !== "Escape" || event.defaultPrevented) return;
  if (escapeStack.length === 0) return;
  event.preventDefault();
  closeTopmostOverlay();
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
    return registerEscapeEntry(entry.current);
  }, [active]);
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Pure focus-wrap rule. Returns the index to focus when Tab would leave the trap, or null to let
 * the browser move focus normally. `current` is -1 when focus is outside the focusable list.
 */
export function nextTrapIndex(count: number, current: number, shiftKey: boolean): number | null {
  if (count <= 0) return null;
  if (shiftKey) return current <= 0 ? count - 1 : null;
  return current === -1 || current >= count - 1 ? 0 : null;
}

export interface AccessibleModalProps {
  open: boolean;
  onClose: () => void;
  /** Accessible name when there is no visible title element. */
  label?: string;
  /** Id of the visible title element (preferred over `label`). */
  labelledBy?: string;
  describedBy?: string;
  /** Close when the backdrop (outside the panel) is pressed. Default false. */
  closeOnBackdrop?: boolean;
  /** Prevent the page behind the modal from scrolling. Default false. */
  lockScroll?: boolean;
  overlayClassName?: string;
  panelClassName?: string;
  children?: React.ReactNode;
}

const DEFAULT_OVERLAY = "p-4 sm:p-6 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200";
const DEFAULT_PANEL =
  "bg-[#090e18] border border-[#1e2d46] rounded-2xl w-full max-w-6xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden";

export const AccessibleModal: React.FC<AccessibleModalProps> = ({
  open,
  onClose,
  label,
  labelledBy,
  describedBy,
  closeOnBackdrop = false,
  lockScroll = false,
  overlayClassName = DEFAULT_OVERLAY,
  panelClassName = DEFAULT_PANEL,
  children,
}) => {
  const panelRef = useRef<HTMLDivElement>(null);
  useEscapeToClose(open, onClose);

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const panel = panelRef.current;
    if (panel && !panel.contains(document.activeElement)) {
      const first = panel.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      (first ?? panel).focus();
    }
    const previousOverflow = document.body.style.overflow;
    if (lockScroll) document.body.style.overflow = "hidden";
    return () => {
      if (lockScroll) document.body.style.overflow = previousOverflow;
      if (previous && previous.isConnected) previous.focus();
    };
  }, [open, lockScroll]);

  if (!open) return null;

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Tab" || event.defaultPrevented) return;
    const panel = panelRef.current;
    if (!panel) return;
    const focusables = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
    if (focusables.length === 0) {
      event.preventDefault();
      panel.focus();
    } else {
      const target = nextTrapIndex(focusables.length, focusables.indexOf(document.activeElement as HTMLElement), event.shiftKey);
      if (target !== null) {
        event.preventDefault();
        focusables[target].focus();
      }
    }
    event.stopPropagation(); // a nested modal must not be re-handled by its parent trap
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center ${overlayClassName}`}
      onMouseDown={closeOnBackdrop ? (event) => { if (event.target === event.currentTarget) onClose(); } : undefined}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={labelledBy ? undefined : label}
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        tabIndex={-1}
        className={panelClassName}
        onKeyDown={handleKeyDown}
      >
        {children}
      </div>
    </div>
  );
};
