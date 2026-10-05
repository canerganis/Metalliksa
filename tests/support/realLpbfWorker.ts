import { once } from 'node:events';
import { rm } from 'node:fs/promises';
import { LpbfWorkerUnavailableError, lpbfWorker } from '../../server/lpbfWorkerBridge';

// Thrown by the bridge's send() only when the caller's own request budget is exhausted.
const CALLER_DEADLINE_ERRORS = new Set(['LPBF worker request deadline exceeded', 'LPBF worker RPC timeout']);

/** Warm up the real worker before timed work. A cold start (WSL, or a loaded host) can outlast one request's
 * 20 s budget; such callers get LPBF_WORKER_STARTING and retry. When readiness lands in the last moments of a
 * caller's budget, the capabilities RPC itself is left no time and fails with a caller-deadline error (seen as
 * "LPBF worker request deadline exceeded" at 20.6 s under two concurrent suites); the next attempt has a full
 * budget. Any other failure, such as a worker that exited, is thrown at once. */
export async function waitForRealWorker(deadline: number) {
  for (;;) {
    // Each attempt is also capped at the remaining warm-up budget, so the warm-up cannot overrun its deadline
    // by up to one request budget (20 s). The capped request keeps running in the bridge; its late outcome is
    // observed and ignored.
    const attempt = lpbfWorker.request('capabilities');
    attempt.catch(() => {});
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      return await Promise.race([attempt, new Promise<never>((_resolve, reject) => {
        timer = setTimeout(() => reject(new Error('LPBF worker was not ready within the warm-up deadline')),
          Math.max(0, deadline - Date.now()));
      })]);
    } catch (error) {
      const retryable = error instanceof LpbfWorkerUnavailableError
        && (error.code === 'LPBF_WORKER_STARTING' || CALLER_DEADLINE_ERRORS.has(error.message));
      if (!retryable || Date.now() >= deadline) throw error;
      await new Promise(resolve => setTimeout(resolve, Math.min(250, Math.max(0, deadline - Date.now()))));
    } finally { clearTimeout(timer); }
  }
}

/** Run one worker call, retrying only failures that cannot have changed worker state, until `deadline`.
 * LPBF_WORKER_STARTING means the request was never written to the worker, so it is always safe to retry. A
 * caller-deadline error ("RPC timeout") means the request may already have been delivered, so it is retried only
 * for idempotent calls (get, capabilities, archive-capture) and never for submit. Anything else, and any
 * failure at the deadline, is thrown unchanged, so a broken worker still fails with its own message. */
export async function retryWorkerCall<T>(call: () => Promise<T>, deadline: number, options: { idempotent: boolean }): Promise<T> {
  for (;;) {
    try { return await call(); }
    catch (error) {
      const retryable = error instanceof LpbfWorkerUnavailableError
        && (error.code === 'LPBF_WORKER_STARTING' || (options.idempotent && CALLER_DEADLINE_ERRORS.has(error.message)));
      if (!retryable || Date.now() >= deadline) throw error;
      await new Promise(resolve => setTimeout(resolve, Math.min(250, Math.max(0, deadline - Date.now()))));
    }
  }
}

/** Run every teardown step even when an earlier one fails (for example stopRealWorker hitting its 10 s bound),
 * so the environment is restored, the HTTP server closed and the temp root removed; then fail loudly with the
 * first error (all errors when several steps failed). */
export async function runCleanupSteps(steps: Array<() => unknown>) {
  const errors: unknown[] = [];
  for (const step of steps) {
    try { await step(); } catch (error) { errors.push(error); }
  }
  if (errors.length === 1) throw errors[0];
  if (errors.length > 1) throw new AggregateError(errors, `${errors.length} teardown steps failed`);
}

function restoreEnv(name: string, value: string | undefined) {
  if (value === undefined) delete process.env[name];
  else process.env[name] = value;
}

/** Point the shared real LPBF worker at a per-test job root. The bridge reads it at each launch, and for a WSL
 * worker lpbfWorkerCommand forwards it through WSLENV (server/pythonRuntime.ts). Before that forwarding, the WSL
 * worker ignored the per-test root, used the checkout's shared .lpbf-jobs and collided with any other worker on
 * that checkout. Returns a restore function. */
export function isolateWorkerJobRoot(jobRoot: string): () => void {
  const prior = process.env.METALLIKSA_JOB_ROOT;
  process.env.METALLIKSA_JOB_ROOT = jobRoot;
  return () => restoreEnv('METALLIKSA_JOB_ROOT', prior);
}

/** Close the real worker and wait until its process has exited. The bridge escalates to SIGKILL after 1 s, so
 * the 10 s bound only turns a leaked worker into a loud teardown failure instead of a hang. */
export async function stopRealWorker() {
  const child = (lpbfWorker as unknown as { process?: NodeJS.EventEmitter & { exitCode: number | null; signalCode: string | null } }).process;
  const exited = child && child.exitCode === null && child.signalCode === null ? once(child, 'exit') : undefined;
  lpbfWorker.close();
  if (!exited) return;
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    await Promise.race([exited, new Promise((_resolve, reject) => {
      timer = setTimeout(() => reject(new Error('LPBF worker did not exit within 10 s of close()')), 10_000);
    })]);
  } finally { clearTimeout(timer); }
}

/** Remove a test root that the worker used. The interpreter holding jobs/worker.lock and queue.sqlite can outlive
 * the 'exit' of the bridge's direct child when that child is a launcher (py.exe, a venv Scripts\python.exe):
 * the launcher's job object kills it asynchronously, and the lock was released about 100 ms later under load.
 * rmSync cannot wait for that on Node 24 Windows: it failed after 0 ms with "EPERM, Permission denied" despite
 * maxRetries. The async rm honours maxRetries for EPERM/EBUSY (linear backoff, at most 5.5 s here). */
export async function removeWorkerTestRoot(root: string) {
  await rm(root, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
