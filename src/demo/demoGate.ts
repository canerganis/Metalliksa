/**
 * Pure gates of the static demo (docs/DEMO_STATIC_DESIGN.md sections 4 and 5).
 * No import.meta access here, so tests import this file directly. Production code calls these only
 * behind the compile-time IS_STATIC_DEMO constant, so a normal build drops them.
 */
import { DEMO_MODULES } from './demoModules.ts';

export const UNAVAILABLE_TEXT = 'Not available in the static demo.';
export const LOCKED_TITLE = 'Recorded values only in the static demo.';
export const HIDDEN_MODULE_NOTE = 'That module is not part of the static demo.';
export const FINGERPRINT_MISMATCH_TEXT = 'The recorded snapshots do not match the bundled calibration data (implementation fingerprint differs), so this view is hidden.';
/** Props that lock a control to the recorded values. */
export const DEMO_LOCK: { readonly disabled: true; readonly title: string } = { disabled: true, title: LOCKED_TITLE };

/** Props for a control whose action needs a live engine, a download or a write. */
export const DEMO_UNAVAILABLE_LOCK: { readonly disabled: true; readonly title: string } = { disabled: true, title: UNAVAILABLE_TEXT };

/** Navigation, palette and counters read the filtered list. The home page is not a module and is unaffected. */
export function visibleModules<T extends { readonly id: string }>(modules: readonly T[]): T[] {
  return modules.filter(module => DEMO_MODULES.includes(module.id));
}

/** First path segment of a hash like "#/id?tab=x". */
export function hashModuleId(hash: string): string {
  return hash.replace(/^#\/?/, '').split(/[?/]/)[0];
}

/**
 * A hash that names a registry module outside the allowlist goes home. Unknown ids are not hidden ids: they keep
 * the app's own handling. Must run before App maps unknown hashes to 3d-distortion-lab.
 */
export function hiddenModuleRedirect(hash: string, isRegistryId: (id: string) => boolean): string | null {
  const id = hashModuleId(hash);
  return id && isRegistryId(id) && !DEMO_MODULES.includes(id) ? '#/home' : null;
}

export type FingerprintStatus = 'match' | 'mismatch' | 'unknown';

/** Snapshot index fingerprint against the bundled error-bands implementationHash. A missing side is unknown, never a match. */
export function fingerprintStatus(indexFingerprint: unknown, bundledHash: unknown): FingerprintStatus {
  if (typeof indexFingerprint !== 'string' || typeof bundledHash !== 'string' || !indexFingerprint || !bundledHash) return 'unknown';
  return indexFingerprint.toLowerCase() === bundledHash.toLowerCase() ? 'match' : 'mismatch';
}

/** Only a proven mismatch hides the cards; an unreadable index is already handled by the per-request misses. */
export function hidesCalibrationViews(status: FingerprintStatus): boolean {
  return status === 'mismatch';
}

/** Repository link in the demo banner. The banner sentence itself is fixed (docs/DEMO_STATIC_DESIGN.md section 6). */
export const DEMO_REPO_URL = 'https://github.com/canerganis/metalliksa';

/** The index.json fields the banner and the report header read. Anything else in the index is ignored. */
export interface SnapshotIndexInfo {
  readonly appVersion?: unknown;
  readonly gitCommit?: unknown;
  readonly fingerprint?: unknown;
}

/**
 * The exact banner sentence (section 6): "Static snapshot of version X, computed offline. Not live solver output."
 * X is appVersion plus the short commit from index.json, for example "0.1.0 (d0f9795)". A missing or malformed
 * field gives "unknown" for that part, never a made up value.
 */
export function demoBannerText(info: SnapshotIndexInfo | null | undefined): string {
  const version = typeof info?.appVersion === 'string' && info.appVersion.trim() ? info.appVersion.trim() : 'unknown';
  const commit = typeof info?.gitCommit === 'string' && info.gitCommit.trim() ? info.gitCommit.trim() : '';
  const label = commit ? `${version} (${commit})` : version;
  return `Static snapshot of version ${label}, computed offline. Not live solver output.`;
}

/** First eight characters of the recorded fingerprint, shown on hover in the banner. */
export function fingerprintPrefix(info: SnapshotIndexInfo | null | undefined): string {
  return typeof info?.fingerprint === 'string' && info.fingerprint.length >= 8 ? info.fingerprint.slice(0, 8) : 'unknown';
}
