/**
 * Non-dismissible banner of the static demo (docs/DEMO_STATIC_DESIGN.md section 6). App mounts it above the
 * module area, so no module can hide it. Used by production code only behind IS_STATIC_DEMO.
 */
import React, { useEffect, useState } from 'react';
import { DEMO_REPO_URL, demoBannerText, fingerprintPrefix, type SnapshotIndexInfo } from './demoGate.ts';

let infoPromise: Promise<SnapshotIndexInfo | null> | null = null;
/** Reads appVersion, gitCommit and fingerprint from the copied snapshot index. Null when it cannot be read. */
export function loadSnapshotIndexInfo(): Promise<SnapshotIndexInfo | null> {
  infoPromise ??= fetch(`${import.meta.env.BASE_URL}demo-snapshots/index.json`)
    .then(res => (res.ok ? res.json() : null))
    .then(index => (index && typeof index === 'object' ? (index as SnapshotIndexInfo) : null))
    .catch(() => null);
  return infoPromise;
}

/** Banner with the exact sentence, a repository link and the fingerprint prefix on hover. `info` skips the fetch (tests). */
export function DemoBanner({ info }: { info?: SnapshotIndexInfo | null }) {
  const [loaded, setLoaded] = useState<SnapshotIndexInfo | null>(info ?? null);
  useEffect(() => {
    if (info !== undefined) return;
    let live = true;
    void loadSnapshotIndexInfo().then(result => { if (live) setLoaded(result); });
    return () => { live = false; };
  }, [info]);
  const current = info !== undefined ? info : loaded;
  return (
    <aside aria-label="Static demo notice" data-testid="demo-banner" title={`Recorded fingerprint ${fingerprintPrefix(current)}`}
      className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-100 lg:px-6">
      <p className="m-0">{demoBannerText(current)} <a href={DEMO_REPO_URL} className="underline underline-offset-2 hover:text-amber-50" rel="noopener noreferrer">Repository</a></p>
    </aside>
  );
}
