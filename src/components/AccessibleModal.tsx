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

type EscapeEntry = { current: () => void; seq?: number };

// Open overlays register here ordered by open sequence number (not effect order), so the most
// recently opened overlay is topmost even when a child effect runs before its parent in one commit.
const escapeStack: EscapeEntry[] = [];
let listenerInstalled = false;
let openCounter = 0;

/** Monotonic sequence number; take one when an overlay opens (render time). */
export function nextOpenSeq(): number {
  openCounter += 1;
  return openCounter;
}

/** Pure: inserts entry keeping the stack sorted by seq (entries without seq go on top, in order). */
export function insertByOpenOrder(stack: EscapeEntry[], entry: EscapeEntry): void {
  const seq = entry.seq;
  if (seq === undefined) {
    stack.push(entry);
    return;
  }
  let index = stack.length;
  while (index > 0) {
    const prev = stack[index - 1].seq;
    if (prev !== undefined && prev > seq) index -= 1;
    else break;
  }
  stack.splice(index, 0, entry);
}

/** Registers an overlay on the stack; returns the unregister function. */
export function registerEscapeEntry(entry: EscapeEntry): () => void {
  insertByOpenOrder(escapeStack, entry);
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
  // Sequence is taken at render time (parents render before children), reset when closed.
  if (!active) entry.current.seq = undefined;
  else if (entry.current.seq === undefined) entry.current.seq = nextOpenSeq();

  useEffect(() => {
    if (!active) return undefined;
    return registerEscapeEntry(entry.current);
  }, [active]);
}

const FOCUSABLE_SELECTOR =
  'a[href], button, input:not([type="hidden"]), select, textarea, [tabindex], [contenteditable]:not([contenteditable="false"])';

/** Minimal element shape used by the tabbable predicate (lets tests use plain objects). */
export interface TabbableCandidate {
  disabled?: boolean;
  hidden?: boolean;
  tabIndex?: number;
  inert?: boolean;
  hasInertAncestor?: boolean;
  /** true when the element has no layout box (display:none / visibility:hidden / detached). */
  notRendered?: boolean;
}

/** Pure rule: is this candidate actually reachable with Tab? */
export function isTabbableCandidate(c: TabbableCandidate): boolean {
  if (c.disabled || c.hidden || c.inert || c.hasInertAncestor || c.notRendered) return false;
  if (typeof c.tabIndex === "number" && c.tabIndex < 0) return false;
  return true;
}

function toCandidate(el: HTMLElement): TabbableCandidate {
  let notRendered = false;
  if (typeof window !== "undefined" && typeof window.getComputedStyle === "function") {
    const style = window.getComputedStyle(el);
    const hasBox = el.getClientRects().length > 0 || el.offsetParent !== null;
    notRendered = style.visibility === "hidden" || style.display === "none" || !hasBox;
  }
  return {
    disabled: (el as HTMLButtonElement).disabled === true,
    hidden: el.hidden || el.closest("[hidden]") !== null,
    tabIndex: el.tabIndex,
    inert: (el as HTMLElement & { inert?: boolean }).inert === true,
    hasInertAncestor: el.closest("[inert]") !== null,
    notRendered,
  };
}

/** Returns the elements inside `root` that Tab can actually reach. Browser-only (DOM). */
export function getTabbableElements(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter((el) => isTabbableCandidate(toCandidate(el)));
}

/**
 * Pure focus-wrap rule. Returns the index to focus when Tab would leave the trap, or null to let
 * the browser move focus normally. `current` is -1 when focus is outside the focusable list.
 */
export function nextTrapIndex(count: number, current: number, shiftKey: boolean): number | null {
  if (count <= 0) return null;
  if (shiftKey) return current <= 0 ? count - 1 : null;
  return current === -1 || current >= count - 1 ? 0 : null;
}

export interface FocusMemory<T = unknown> {
  opened: boolean;
  previous: T | null;
}

/** Pure: records the focused element once per open, before any child autoFocus can move focus. */
export function rememberFocusOnOpen<T>(memory: FocusMemory<T>, open: boolean, active: T | null): void {
  if (open && !memory.opened) {
    memory.opened = true;
    memory.previous = active;
  }
}

/** Pure: returns the element to restore and resets the memory for the next open. */
export function takeFocusMemory<T>(memory: FocusMemory<T>): T | null {
  const previous = memory.previous;
  memory.opened = false;
  memory.previous = null;
  return previous;
}

/**
 * Pure backdrop rule (previous click semantics): close only for a primary-button click whose press
 * started on the overlay itself and whose click target is the overlay itself.
 */
export function shouldCloseOnBackdropClick(input: { pressStartedOnOverlay: boolean; targetIsOverlay: boolean; button: number }): boolean {
  return input.button === 0 && input.pressStartedOnOverlay && input.targetIsOverlay;
}

export interface ScrollLockState {
  count: number;
  original: string;
}

/** Pure ref-counted lock step: stores the original value at 0->1. */
export function acquireScrollLock(state: ScrollLockState, currentOverflow: string): void {
  if (state.count === 0) state.original = currentOverflow;
  state.count += 1;
}

/** Returns the value to restore at 1->0, otherwise null. */
export function releaseScrollLock(state: ScrollLockState): string | null {
  if (state.count === 0) return null;
  state.count -= 1;
  return state.count === 0 ? state.original : null;
}

const scrollLockState: ScrollLockState = { count: 0, original: "" };
let devWarned = false;

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
  const focusMemory = useRef<FocusMemory<HTMLElement>>({ opened: false, previous: null });
  const pressStartedOnOverlay = useRef(false);
  useEscapeToClose(open, onClose);
  // Render phase on purpose: React applies a child's autoFocus during commit, before any effect of this
  // component runs, so the previously focused element must be captured before that.
  rememberFocusOnOpen(
    focusMemory.current,
    open,
    typeof document !== "undefined" && document.activeElement instanceof HTMLElement ? document.activeElement : null,
  );

  // Focus management: depends only on `open`, so toggling other props never moves focus.
  useEffect(() => {
    if (!open) return undefined;
    const memory = focusMemory.current;
    const panel = panelRef.current;
    if (panel && !panel.contains(document.activeElement)) {
      const first = getTabbableElements(panel)[0];
      (first ?? panel).focus();
    }
    return () => {
      const previous = takeFocusMemory(memory);
      if (previous && previous.isConnected) previous.focus();
    };
  }, [open]);

  // Scroll lock: module-level ref count shared by all modals.
  useEffect(() => {
    if (!open || !lockScroll) return undefined;
    acquireScrollLock(scrollLockState, document.body.style.overflow);
    document.body.style.overflow = "hidden";
    return () => {
      const restore = releaseScrollLock(scrollLockState);
      if (restore !== null) document.body.style.overflow = restore;
    };
  }, [open, lockScroll]);

  if (!devWarned && !label && !labelledBy && typeof process !== "undefined" && process.env?.NODE_ENV !== "production") {
    devWarned = true;
    console.warn("AccessibleModal: provide `label` or `labelledBy` so the dialog has an accessible name.");
  }

  if (!open) return null;

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Tab" || event.defaultPrevented) return;
    const panel = panelRef.current;
    if (!panel) return;
    const focusables = getTabbableElements(panel);
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
      onMouseDown={closeOnBackdrop ? (event) => { pressStartedOnOverlay.current = event.button === 0 && event.target === event.currentTarget; } : undefined}
      onClick={
        closeOnBackdrop
          ? (event) => {
              const started = pressStartedOnOverlay.current;
              pressStartedOnOverlay.current = false;
              if (shouldCloseOnBackdropClick({ pressStartedOnOverlay: started, targetIsOverlay: event.target === event.currentTarget, button: event.button })) onClose();
            }
          : undefined
      }
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
