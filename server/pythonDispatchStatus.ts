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

/**
 * The solver's JSON document from stdout. Libraries imported by a solver (NVIDIA Warp prints an init banner and
 * kernel-cache lines) can write to stdout before the result. When the whole text is not JSON, the document is the
 * text from the first line that begins with "{" at column 0 to the end (one-line or indented JSON alike). Returns
 * null when there is no such document; the caller then keeps rawOutput.
 */
export function parsePythonStdout(stdout: string): unknown | null {
  try {
    return JSON.parse(stdout);
  } catch {
    const lines = stdout.split(/\r?\n/);
    for (let i = 0; i < lines.length; i++) {
      if (!lines[i].startsWith("{")) continue;
      try {
        return JSON.parse(lines.slice(i).join("\n"));
      } catch {
        // a "{" line that does not start the final document; keep looking
      }
    }
    return null;
  }
}
