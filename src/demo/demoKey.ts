/**
 * Canonical request key shared by the runtime demo fetch and the snapshot generator (WP2).
 * Pure functions, no DOM, no Node APIs: both sides import this file so the keys cannot drift.
 *
 * Key = `METHOD path[?sorted query] canonicalJson(body)`.
 * Object keys are sorted recursively, `undefined` members are dropped, -0 becomes 0, non-finite numbers
 * become null (as JSON does). Numbers are not rounded: JSON.stringify prints the shortest round-trip form.
 */

/**
 * Fields the client generates per call. They are removed at any depth before the key is built, otherwise
 * every guided request would miss. WP2 mirrors this list in scripts/demo/demo-requests.json and a shared
 * fixture proves that two requests differing only in these fields give the same key.
 */
export const DEFAULT_EXCLUDED_FIELDS: readonly string[] = [
  'requestId',
  'clientRequestId',
  'clientTimestamp',
  'jobId',
  'runId',
  'nonce',
  'idempotencyKey',
];

export function canonicalize(value: unknown, excluded: ReadonlySet<string>): unknown {
  if (value === null) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? (Object.is(value, -0) ? 0 : value) : null;
  if (Array.isArray(value)) return value.map(item => (item === undefined ? null : canonicalize(item, excluded)));
  if (typeof value === 'object') {
    const source = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const name of Object.keys(source).sort()) {
      if (excluded.has(name) || source[name] === undefined) continue;
      out[name] = canonicalize(source[name], excluded);
    }
    return out;
  }
  return value;
}

export function canonicalJson(value: unknown, excludedFields: readonly string[] = DEFAULT_EXCLUDED_FIELDS): string {
  const canonical = canonicalize(value, new Set(excludedFields));
  return canonical === undefined ? '' : JSON.stringify(canonical);
}

/** Query string with parameters sorted by name then value, or '' when there are none. */
export function canonicalQuery(search: string): string {
  const params = new URLSearchParams(search);
  const pairs = [...params.entries()].sort((a, b) => (a[0] === b[0] ? (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0) : a[0] < b[0] ? -1 : 1));
  if (pairs.length === 0) return '';
  return '?' + pairs.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
}

/** `body` is the parsed JSON body, or undefined/null when there is none. Text bodies that are not JSON are keyed by the raw string. */
export function requestKey(
  method: string,
  pathname: string,
  search: string,
  body: unknown,
  excludedFields: readonly string[] = DEFAULT_EXCLUDED_FIELDS,
): string {
  const bodyPart = body === undefined || body === null ? '' : canonicalJson(body, excludedFields);
  return `${method.toUpperCase()} ${pathname}${canonicalQuery(search)} ${bodyPart}`.trimEnd();
}
