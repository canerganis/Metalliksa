/**
 * Air-gap / offline mode: AIRGAPPED=1 disables outbound cloud services.
 * Local Python LPBF / CALPHAD / EIS remain available.
 */

export type AirgapBlockedService =
  | "GPT-6 AI (copilot / micrograph vision)"
  | "NVIDIA cloud NIM / DeepSeek endpoints"
  | "Materials Project live DFT API (reserved, not implemented)"
  | "External powder / pricing APIs (reserved, not implemented)"
  | "Crossref literature search";

// Entries marked "(reserved, not implemented)" are policy slots with no code behind them yet;
// they stay listed so a future integration is blocked by default when AIRGAPPED=1.
export const AIRGAP_BLOCKED_SERVICES: AirgapBlockedService[] = [
  "GPT-6 AI (copilot / micrograph vision)",
  "NVIDIA cloud NIM / DeepSeek endpoints",
  "Materials Project live DFT API (reserved, not implemented)",
  "External powder / pricing APIs (reserved, not implemented)",
  "Crossref literature search",
];

export const AIRGAP_ALLOWED_LOCAL = [
  "Local LPBF build-job (Rosenthal screening + slicer)",
  "Local Python physics (CALPHAD / EIS / kinetics when installed)",
  "Bundled Materials Project reference catalog (offline copy)",
] as const;

export function isAirgappedFromEnv(env: NodeJS.ProcessEnv | Record<string, string | undefined> = process.env): boolean {
  const raw = String(env.AIRGAPPED ?? env.VITE_AIRGAPPED ?? "").trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes" || raw === "on";
}

export function airgapDenyPayload(service: string) {
  return {
    error: `Air-gap mode (AIRGAPPED=1): ${service} is disabled. Local LPBF and physics engines remain available.`,
    airgapped: true,
    blockedService: service,
    blockedServices: AIRGAP_BLOCKED_SERVICES,
    allowedLocal: AIRGAP_ALLOWED_LOCAL,
  };
}

export class AirgapBlockedError extends Error {
  readonly airgapped = true as const;
  readonly blockedService: string;
  constructor(service: string) {
    super(`Air-gap mode (AIRGAPPED=1): ${service} is disabled.`);
    this.name = "AirgapBlockedError";
    this.blockedService = service;
  }
}

/** Structural guard for service modules: throws before any outbound network call when air-gapped. */
export function assertNotAirgapped(service: string, env: NodeJS.ProcessEnv | Record<string, string | undefined> = process.env): void {
  if (isAirgappedFromEnv(env)) throw new AirgapBlockedError(service);
}
