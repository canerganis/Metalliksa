/**
 * Plain notes of the static demo (docs/DEMO_STATIC_DESIGN.md section 5). Imports only text constants, so
 * a chunk that references it stays light. Used by production components only behind IS_STATIC_DEMO.
 */
import React, { useEffect, useRef } from 'react';
import { HIDDEN_MODULE_NOTE, LOCKED_TITLE, UNAVAILABLE_TEXT } from './demoGate.ts';

/** Note shown in place of a panel that needs a live engine or free input. */
export function DemoUnavailable({ what }: { what?: string }) {
  return <p role="status" data-testid="demo-unavailable" className="rounded-lg border border-slate-700 bg-slate-900/40 p-4 text-sm text-slate-300">{what ? `${what}: ` : ''}{UNAVAILABLE_TEXT}</p>;
}

/** Note shown on the start page after a hidden module link was redirected home. */
export function DemoRedirectNote() {
  return <p role="status" data-testid="demo-hidden-note" className="mb-4 rounded-lg border border-cyan-500/20 px-4 py-3 text-xs text-cyan-200">{HIDDEN_MODULE_NOTE}</p>;
}

/**
 * Locks every control inside to the recorded values: a disabled fieldset (display: contents, so layout is unchanged)
 * plus the "Recorded values only in the static demo." title on each control. Use for sections whose inputs would feed
 * an endpoint that has no snapshot.
 */
export function DemoLock({ children }: { children?: React.ReactNode }) {
  const ref = useRef<HTMLFieldSetElement>(null);
  useEffect(() => {
    ref.current?.querySelectorAll('input, select, textarea, button').forEach(control => { if (!control.getAttribute('title')) control.setAttribute('title', LOCKED_TITLE); });
  });
  return <fieldset ref={ref} disabled className="contents m-0 border-0 p-0">{children}</fieldset>;
}
