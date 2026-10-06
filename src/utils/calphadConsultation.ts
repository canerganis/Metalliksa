export class ConsultationResponseError extends Error {
  constructor() {
    super("The consultation service returned no usable text.");
    this.name = "ConsultationResponseError";
  }
}

const RESPONSE_FIELDS = ["response", "text", "answer", "reply"] as const;

export function parseConsultationResponse(payload: unknown): string {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    throw new ConsultationResponseError();
  }

  const response = payload as Record<string, unknown>;
  for (const field of RESPONSE_FIELDS) {
    const value = response[field];
    if (typeof value === "string" && value.trim().length > 0) return value.trim();
  }

  throw new ConsultationResponseError();
}

export class LatestConsultationRequest {
  private current = 0;

  begin(): number {
    this.current += 1;
    return this.current;
  }

  invalidate(): void {
    this.current += 1;
  }

  isCurrent(request: number): boolean {
    return request === this.current;
  }
}
