import { useEffect, useLayoutEffect, useRef } from 'react';

// Global Cmd+K (Apple) / Ctrl+K (other platforms) for the command palette. Kept apart from
// src/utils/commandPalette.ts so the eager index chunk carries only this listener; the palette and its
// ranking load on first open. Closing keys are never handled here (AccessibleModal's escape stack owns them).

export interface ShortcutKeyEvent {
  readonly key: string;
  /** Physical key; "KeyK" also on layouts whose K key types another letter (Cyrillic, Greek, ...). */
  readonly code?: string;
  readonly ctrlKey: boolean;
  readonly metaKey: boolean;
  readonly altKey: boolean;
  readonly shiftKey: boolean;
  readonly isComposing?: boolean;
  readonly keyCode?: number;
}

export function isApplePlatform(platform: string): boolean {
  return /Mac|iPhone|iPad|iPod/i.test(platform);
}

/**
 * Cmd+K on Apple platforms, Ctrl+K elsewhere, without Alt or Shift (Ctrl+Shift+K is a Firefox shortcut).
 * On macOS Ctrl+K stays the text-field "delete to end of line" binding; IME composition keys never count.
 */
export function isPaletteShortcut(event: ShortcutKeyEvent, apple: boolean): boolean {
  if (event.isComposing === true || event.keyCode === 229) return false;
  if (event.altKey || event.shiftKey) return false;
  const modifier = apple ? event.metaKey && !event.ctrlKey : event.ctrlKey && !event.metaKey;
  return modifier && (event.key.toLowerCase() === 'k' || event.code === 'KeyK');
}

/** Visible key hint for the trigger button. */
export function paletteShortcutLabel(apple: boolean): string {
  return apple ? '⌘K' : 'Ctrl K';
}

/** aria-keyshortcuts value of the trigger button. */
export function paletteShortcutKeys(apple: boolean): string {
  return apple ? 'Meta+K' : 'Control+K';
}

/** Shell state that decides whether the palette may open (read when the key is pressed or the button clicked). */
export interface PaletteGate {
  readonly paletteOpen: boolean;
  /** The engine status dialog is requested (open, or its chunk still loading). */
  readonly engineDialogOpen: boolean;
  /** The boot overlay, or its opaque cover while the boot chunk loads, is on screen. */
  readonly bootOverlayOpen: boolean;
  /** A module's own modal is on screen (see visibleModalOpen). */
  readonly moduleModalOpen: boolean;
}

/** The palette never stacks over another modal, and never opens twice. */
export function canOpenPalette(gate: PaletteGate): boolean {
  return !gate.paletteOpen && !gate.engineDialogOpen && !gate.bootOverlayOpen && !gate.moduleModalOpen;
}

export type ShortcutDecision = 'open' | 'swallow' | 'ignore';

/**
 * open: open the palette (and prevent the browser default). swallow: the palette is already open, so the
 * key is kept from the browser wherever focus is inside it (field or Close button). ignore: another modal
 * owns the screen; the browser keeps its own shortcut.
 */
export function paletteShortcutDecision(gate: PaletteGate): ShortcutDecision {
  if (gate.paletteOpen) return 'swallow';
  return canOpenPalette(gate) ? 'open' : 'ignore';
}

/**
 * True when a module's own aria-modal dialog is on screen. Dialogs inside a hidden (visited, inactive)
 * module view do not count, so a dialog left open there does not disable the palette.
 */
export function visibleModalOpen(root: Pick<Document, 'querySelectorAll'> = document): boolean {
  return Array.from(root.querySelectorAll('[role="dialog"][aria-modal="true"]')).some(dialog => dialog.closest('[hidden]') === null);
}

export interface ShortcutTarget {
  readonly gate: () => PaletteGate;
  readonly open: () => void;
}

/** The window keydown listener: decides from the shell state read at key time (latest render). */
export function createShortcutListener(apple: boolean, target: () => ShortcutTarget) {
  return (event: ShortcutKeyEvent & { readonly defaultPrevented: boolean; preventDefault(): void }) => {
    if (event.defaultPrevented || !isPaletteShortcut(event, apple)) return;
    const { gate, open } = target();
    const decision = paletteShortcutDecision(gate());
    if (decision === 'ignore') return;
    event.preventDefault();
    if (decision === 'open') open();
  };
}

export function useCommandPaletteShortcut(apple: boolean, gate: () => PaletteGate, open: () => void): void {
  const latest = useRef<ShortcutTarget>({ gate, open });
  useLayoutEffect(() => {
    latest.current = { gate, open };
  });
  useEffect(() => {
    const onKey = createShortcutListener(apple, () => latest.current);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [apple]);
}
