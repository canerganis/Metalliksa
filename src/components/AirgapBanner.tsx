import React, { useEffect, useState } from "react";
import { ShieldAlert, ChevronDown, ChevronUp } from "lucide-react";

export interface RuntimeConfig {
  airgapped: boolean;
  blockedServices: string[];
  allowedLocal: string[];
}

const FALLBACK: RuntimeConfig = {
  airgapped: false,
  blockedServices: [],
  allowedLocal: [],
};

let cached: RuntimeConfig | null = null;
let accessRequired = false;
const accessListeners = new Set<(v: boolean) => void>();
let nativeFetch: typeof fetch | null = null;

function setAccessRequired(v: boolean) {
  if (accessRequired === v) return;
  accessRequired = v;
  accessListeners.forEach((l) => l(v));
}

export async function fetchRuntimeConfig(force = false): Promise<RuntimeConfig> {
  if (cached && !force) return cached;
  try {
    const res = await (nativeFetch ?? fetch)("/api/runtime-config");
    setAccessRequired(res.status === 401);
    if (!res.ok) return cached ?? FALLBACK;
    cached = (await res.json()) as RuntimeConfig;
    return cached;
  } catch {
    return cached ?? FALLBACK;
  }
}

/** Re-check access after any /api call returned 401 (expired session, server restart). */
let recheckPending = false;
function onApiUnauthorized() {
  if (recheckPending) return;
  recheckPending = true;
  void fetchRuntimeConfig(true).finally(() => {
    recheckPending = false;
  });
}

/** True for same-origin /api/ requests other than /api/runtime-config (the only ones that trigger a re-check). */
export function isWatchedApiRequest(input: unknown, origin: string): boolean {
  try {
    const raw = typeof input === "string" ? input : input instanceof URL ? input.href : (input as Request).url;
    const u = new URL(raw, origin);
    if (u.origin !== origin) return false;
    const p = u.pathname.toLowerCase();
    return p.startsWith("/api/") && p !== "/api/runtime-config";
  } catch {
    return false;
  }
}

let installed = false;
/** Wrap window.fetch so a 401 from a same-origin /api call re-checks access. Call once from the app entry. */
export function installApiUnauthorizedWatcher(): void {
  if (installed || typeof window === "undefined" || !window.fetch) return;
  installed = true;
  const original = window.fetch.bind(window);
  nativeFetch = original;
  window.fetch = async (...args: Parameters<typeof fetch>) => {
    const res = await original(...args);
    if (res.status === 401 && isWatchedApiRequest(args[0], window.location.origin)) onApiUnauthorized();
    return res;
  };
}

export function useRuntimeConfig(): RuntimeConfig {
  const [cfg, setCfg] = useState<RuntimeConfig>(cached ?? FALLBACK);
  useEffect(() => {
    void fetchRuntimeConfig().then(setCfg);
  }, []);
  return cfg;
}

function useAccessRequired(): boolean {
  const [required, setRequired] = useState(accessRequired);
  useEffect(() => {
    accessListeners.add(setRequired);
    setRequired(accessRequired);
    return () => {
      accessListeners.delete(setRequired);
    };
  }, []);
  return required;
}

/** Honest banner when AIRGAPPED=1 — lists which cloud services are cut. */
export const AirgapBanner: React.FC = () => {
  const cfg = useRuntimeConfig();
  const required = useAccessRequired();
  const [open, setOpen] = useState(false);
  if (required) {
    return (
      <div role="alert" className="border-b border-red-500/40 bg-red-500/10 text-red-100 px-3 py-2 text-xs font-mono">
        Sign-in required: <a href="/login" className="underline">open the sign-in page</a>, or use the one-time login link printed in the server console.
      </div>
    );
  }
  if (!cfg.airgapped) return null;

  return (
    <div className="border-b border-amber-500/40 bg-amber-500/10 text-amber-100">
      <div className="max-w-[1600px] mx-auto px-3 py-2 flex items-start gap-2">
        <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] font-mono font-bold uppercase tracking-wide">
              Air-gap mode (AIRGAPPED=1)
            </span>
            <span className="text-[10px] font-mono text-amber-200/90">
              Cloud AI / external DFT / pricing APIs disabled · local LPBF open
            </span>
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="inline-flex items-center gap-0.5 text-[10px] font-mono text-amber-100 underline"
            >
              {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              Services
            </button>
          </div>
          {open && (
            <div className="mt-1.5 grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px] font-mono">
              <div>
                <div className="text-amber-200/70 uppercase mb-0.5">Blocked</div>
                <ul className="list-disc pl-4 space-y-0.5">
                  {(cfg.blockedServices.length ? cfg.blockedServices : ["GPT-6", "NVIDIA", "Materials Project live", "External pricing"]).map(
                    (s) => (
                      <li key={s}>{s}</li>
                    )
                  )}
                </ul>
              </div>
              <div>
                <div className="text-emerald-200/80 uppercase mb-0.5">Still available</div>
                <ul className="list-disc pl-4 space-y-0.5 text-emerald-100/90">
                  {(cfg.allowedLocal.length
                    ? cfg.allowedLocal
                    : ["Local LPBF build-job", "Local Python physics"]
                  ).map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
