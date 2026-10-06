/**
 * Pure staleness decisions for the LPBF engineering result.
 *
 * A result is "fresh" only while the signature of the inputs it was computed for
 * (`resultSignature`, recorded when that job completed) equals the signature of the
 * current draft inputs. Any other combination is stale; the UI must then mark the
 * result as computed for earlier inputs. No scientific content lives here.
 */
export type LpbfJobStatus = string | undefined;

/** True when a result is shown for inputs other than the current draft. */
export function isResultStale(resultSignature: string, currentSignature: string, hasResult = true): boolean {
  return hasResult && resultSignature !== currentSignature;
}

/** Signature that a freshly submitted job's result belongs to: only an already-completed (cached) job owns one. */
export function resultSignatureOnSubmit(status: LpbfJobStatus, submittedSignature: string): string {
  return status === "completed" ? submittedSignature : "";
}

/**
 * Signature to record when polling observes a job state. Completion binds the result to the
 * signature that was SUBMITTED (not the current draft), so edits made during execution leave the
 * finished result stale. Non-terminal observations change nothing (returns undefined).
 */
export function resultSignatureOnPoll(status: LpbfJobStatus, submittedSignature: string): string | undefined {
  return status === "completed" ? submittedSignature : undefined;
}

/** Signature to record when a saved job is restored after a reload. */
export function resultSignatureOnRestore(status: LpbfJobStatus, savedSignature: string | undefined): string {
  return status === "completed" ? savedSignature || "" : "";
}
