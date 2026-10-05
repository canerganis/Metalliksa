import { LatestConsultationRequest } from "./calphadConsultation";

export interface CopilotRequestLease {
  id: number;
  signal: AbortSignal;
}

/** Coordinates cancellation and stale-response rejection for one mounted Copilot conversation. */
export class CopilotRequestLifecycle {
  private readonly requests = new LatestConsultationRequest();
  private controller: AbortController | null = null;

  begin(): CopilotRequestLease {
    this.controller?.abort();
    const controller = new AbortController();
    this.controller = controller;
    return { id: this.requests.begin(), signal: controller.signal };
  }

  invalidate(): void {
    this.requests.invalidate();
    this.controller?.abort();
    this.controller = null;
  }

  isCurrent(request: CopilotRequestLease): boolean {
    return !request.signal.aborted && this.requests.isCurrent(request.id);
  }
}
