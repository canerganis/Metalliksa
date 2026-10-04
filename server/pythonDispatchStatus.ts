/**
 * HTTP status for a parsed Python solver result (DESIGN-6a section 2, "Bridge").
 *
 * Only the Phase 6a validation envelope changes the status: `errorKind: "validation"`
 * (printed by migrated solvers with exit code 2) -> 422, body unchanged.
 *
 * Every other outcome keeps the pre-Phase-6a behaviour (HTTP 200 with the parsed
 * body, whatever the exit code or a top-level `error`), because existing frontends
 * read that body. A generic 500 mapping is deliberately not applied here.
 */
export function pythonDispatchStatus(parsed: unknown): number {
  const body = parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)
    ? (parsed as Record<string, unknown>)
    : null;
  return body && body.errorKind === "validation" ? 422 : 200;
}
