// Whether the boot overlay is on screen, for shell decisions taken outside the lazy boot chunk (the
// command palette must not open over it). Starts true: from the first paint the opaque boot cover or the
// overlay is shown. BootSequence reports every change; App clears it if the boot chunk fails to load
// (SilentBoundary then shows the shell without a boot screen).
let open = true;

export function isBootOverlayOpen(): boolean {
  return open;
}

export function setBootOverlayOpen(value: boolean): void {
  open = value;
}
