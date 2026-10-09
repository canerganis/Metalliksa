/**
 * window.fetch wrapper for the static demo (docs/DEMO_STATIC_DESIGN.md section 3).
 * Answers same-origin `/api/...` calls from recorded snapshots and nothing else. A call with no snapshot
 * gets a JSON 404 `{error, errorKind: "demo-snapshot-missing"}`: no invented value, no nearest neighbour.
 * Everything that is not a same-origin /api call goes to the native fetch untouched.
 */
import { DEFAULT_EXCLUDED_FIELDS, requestKey } from './demoKey.ts';

export const SNAPSHOT_DIR = 'demo-snapshots';
export const MISSING_KIND = 'demo-snapshot-missing';
export const WRITE_REFUSED_KIND = 'demo-write-refused';
export const MISSING_MESSAGE = 'Not available in the static demo.';
/** Methods that can only change server state. POST may still look up a snapshot (the engine endpoints are POST). */
const REFUSED_METHODS: ReadonlySet<string> = new Set(['PUT', 'PATCH', 'DELETE']);

export interface DemoSnapshotIndex {
  format: number;
  appVersion?: string;
  gitCommit?: string;
  fingerprint?: string;
  generatedAt?: string;
  entries: Record<string, string>;
}

export interface DemoFetchOptions {
  /** Base URL of the app (import.meta.env.BASE_URL). Snapshots live under `${baseUrl}demo-snapshots/`. */
  baseUrl: string;
  /** The real fetch, used for the index, the snapshot files and any non-/api call. */
  nativeFetch: typeof fetch;
  /** Page origin; requests to another origin are passed through. */
  origin: string;
  excludedFields?: readonly string[];
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

async function readBody(input: RequestInfo | URL, init: RequestInit | undefined): Promise<unknown> {
  let raw: unknown = init?.body;
  if (raw === undefined && typeof Request !== 'undefined' && input instanceof Request) {
    const text = await input.clone().text();
    raw = text === '' ? undefined : text;
  }
  if (raw === undefined || raw === null) return undefined;
  if (typeof raw !== 'string') return undefined; // FormData, Blob and streams are never recorded: they miss.
  try { return JSON.parse(raw); } catch { return raw; }
}

export function createDemoFetch(options: DemoFetchOptions): typeof fetch {
  const { nativeFetch, origin } = options;
  const baseUrl = options.baseUrl.endsWith('/') ? options.baseUrl : options.baseUrl + '/';
  const excluded = options.excludedFields ?? DEFAULT_EXCLUDED_FIELDS;
  let indexPromise: Promise<DemoSnapshotIndex | null> | null = null;

  const loadIndex = (): Promise<DemoSnapshotIndex | null> => {
    if (!indexPromise) {
      indexPromise = (async () => {
        try {
          const res = await nativeFetch(`${baseUrl}${SNAPSHOT_DIR}/index.json`);
          if (!res.ok) return null;
          const parsed = (await res.json()) as DemoSnapshotIndex;
          return parsed && typeof parsed === 'object' && parsed.entries && typeof parsed.entries === 'object' ? parsed : null;
        } catch { return null; }
      })();
    }
    return indexPromise;
  };

  const missing = (method: string, path: string) =>
    jsonResponse({ error: `${MISSING_MESSAGE} (${method} ${path})`, errorKind: MISSING_KIND }, 404);

  return async function demoFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    let url: URL;
    try {
      const raw = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
      url = new URL(raw, origin + '/');
    } catch {
      return nativeFetch(input, init);
    }
    if (url.origin !== origin || !url.pathname.startsWith('/api/')) return nativeFetch(input, init);

    const method = (init?.method ?? (typeof Request !== 'undefined' && input instanceof Request ? input.method : 'GET')).toUpperCase();
    if (REFUSED_METHODS.has(method)) {
      return jsonResponse({ error: 'Writes are not served in the static demo.', errorKind: WRITE_REFUSED_KIND }, 405);
    }

    const body = await readBody(input, init);
    const key = requestKey(method, url.pathname, url.search, body, excluded);
    const index = await loadIndex();
    const file = index && Object.prototype.hasOwnProperty.call(index.entries, key) ? index.entries[key] : undefined;
    if (!file) return missing(method, url.pathname);
    try {
      const res = await nativeFetch(`${baseUrl}${SNAPSHOT_DIR}/${file}`);
      if (!res.ok) return missing(method, url.pathname);
      const snapshot = (await res.json()) as { response?: unknown };
      if (snapshot.response === undefined) return missing(method, url.pathname);
      return jsonResponse(snapshot.response, 200);
    } catch {
      return missing(method, url.pathname);
    }
  } as typeof fetch;
}

/** Replaces window.fetch once. Install before anything else wraps fetch. */
export function installDemoFetch(baseUrl: string): void {
  if (typeof window === 'undefined') return;
  const w = window as Window & { __demoFetchInstalled?: boolean };
  if (w.__demoFetchInstalled) return;
  w.__demoFetchInstalled = true;
  w.fetch = createDemoFetch({ baseUrl, nativeFetch: w.fetch.bind(w), origin: w.location.origin });
}
