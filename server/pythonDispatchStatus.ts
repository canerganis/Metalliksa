/**
 * HTTP status for a parsed Python solver result (DESIGN-6a section 2, "Bridge").
 *
 * - `errorKind: "validation"` (stdout envelope of a migrated solver, exit code 2)
 *   -> 422, body is the envelope unchanged.
 * - a non-zero / signalled exit code (null = killed by a signal) -> 500.
 * - a top-level `error` without `success: true` -> 500.
 * - anything else -> 200 (successful results are unchanged).
 *
 * An `exitCode` of `undefined` means the runner did not report one; it is not
 * treated as a failure.
 */
export function pythonDispatchStatus(parsed: unknown, exitCode: number | null | undefined): number {
  const body = parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)
    ? (parsed as Record<string, unknown>)
    : null;
  if (body && body.errorKind === "validation") {
    return 422;
  }
  if (exitCode !== undefined && exitCode !== 0) {
    return 500;
  }
  if (body && body.error !== undefined && body.error !== null && body.error !== false && body.success !== true) {
    return 500;
  }
  return 200;
}
