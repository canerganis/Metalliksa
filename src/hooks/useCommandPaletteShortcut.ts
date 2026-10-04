import { useEffect, useRef } from 'react';

// Global Ctrl/Cmd+K for the command palette. Kept apart from src/utils/commandPalette.ts so the
// eager index chunk carries only this listener; the palette and its ranking load on first open.

export interface ShortcutKeyEvent {
  readonly key: string;
  readonly ctrlKey: boolean;
  readonly metaKey: boolean;
  readonly altKey: boolean;
  readonly shiftKey: boolean;
}

/** Ctrl+K or Cmd+K without Alt or Shift (Ctrl+Shift+K is a browser shortcut in Firefox). */
export function isPaletteShortcut(event: ShortcutKeyEvent): boolean {
  return (event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'k';
}

/** Visible key hint for the trigger button. */
export function paletteShortcutLabel(platform: string): string {
  return /Mac|iPhone|iPad|iPod/i.test(platform) ? '⌘K' : 'Ctrl K';
}

/**
 * Calls `open` on Ctrl/Cmd+K unless a modal dialog (boot screen, engine status, another overlay) is
 * already open: the palette never stacks over a modal, and the shortcut is then left to the browser.
 */
export function useCommandPaletteShortcut(open: () => void): void {
  const latest = useRef(open);
  latest.current = open;
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || !isPaletteShortcut(event)) return;
      if (document.querySelector('[role="dialog"][aria-modal="true"]')) return;
      event.preventDefault();
      latest.current();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
}
