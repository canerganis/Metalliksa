/**
 * Fingerprint guard of the static demo (docs/DEMO_STATIC_DESIGN.md section 4). The snapshot index fingerprint is
 * compared with the bundled error-bands implementationHash. The error bands are loaded with a dynamic import so
 * this module never makes a chunk depend on them. Used by production components only behind IS_STATIC_DEMO.
 */
import React, { useEffect, useState } from 'react';
import { FINGERPRINT_MISMATCH_TEXT, fingerprintStatus, hidesCalibrationViews, type FingerprintStatus } from './demoGate.ts';

let indexPromise: Promise<unknown> | null = null;
function loadIndexFingerprint(): Promise<unknown> {
  indexPromise ??= fetch(`${import.meta.env.BASE_URL}demo-snapshots/index.json`)
    .then(res => (res.ok ? res.json() : null))
    .then(index => (index && typeof index === 'object' ? (index as { fingerprint?: unknown }).fingerprint : null))
    .catch(() => null);
  return indexPromise;
}

async function bundledHash(): Promise<unknown> {
  try { return (await import('../data/lpbfErrorBands')).COMMITTED_ERROR_BANDS?.implementationHash; } catch { return null; }
}

/** Fingerprint state of the loaded snapshots against the bundled error bands. 'unknown' until both sides arrive. */
export function useDemoFingerprintStatus(): FingerprintStatus {
  const [status, setStatus] = useState<FingerprintStatus>('unknown');
  useEffect(() => {
    let live = true;
    void Promise.all([loadIndexFingerprint(), bundledHash()]).then(([fingerprint, hash]) => { if (live) setStatus(fingerprintStatus(fingerprint, hash)); });
    return () => { live = false; };
  }, []);
  return status;
}

/** Hides its children (process window map, calibration scorecard) on a fingerprint mismatch. */
export function DemoFingerprintGate({ children }: { children: React.ReactNode }) {
  const status = useDemoFingerprintStatus();
  if (hidesCalibrationViews(status)) return <p role="alert" data-testid="demo-fingerprint-mismatch" className="rounded-lg border border-amber-500/30 p-4 text-sm text-amber-200">{FINGERPRINT_MISMATCH_TEXT}</p>;
  return <>{children}</>;
}
