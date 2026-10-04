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
    try { return await lpbfWorker.request('capabilities'); }
    catch (error) {
      const retryable = error instanceof LpbfWorkerUnavailableError
        && (error.code === 'LPBF_WORKER_STARTING' || CALLER_DEADLINE_ERRORS.has(error.message));
      if (!retryable || Date.now() > deadline) throw error;
      await new Promise(resolve => setTimeout(resolve, 250));
    }
  }
}

function restoreEnv(name: string, value: string | undefined) {
  if (value === undefined) delete process.env[name];
  else process.env[name] = value;
}

/** Point the shared real LPBF worker at a per-test job root, also when the bridge starts it through WSL.
 * Windows environment variables reach a wsl.exe child only when WSLENV lists them. Without that the WSL worker
 * ignored METALLIKSA_JOB_ROOT, used the checkout's shared .lpbf-jobs, and exited 2 ("Another LPBF worker owns
 * this job root") whenever another worker held it; the bridge then fell back to a host interpreter after the WSL
 * start-up. '/p' translates the Windows path to its /mnt/<drive> form. Returns a restore function. */
export function isolateWorkerJobRoot(jobRoot: string): () => void {
  const prior = { jobRoot: process.env.METALLIKSA_JOB_ROOT, wslenv: process.env.WSLENV };
  const forwarded = (prior.wslenv ?? '').split(':').filter(entry => entry && entry.split('/')[0] !== 'METALLIKSA_JOB_ROOT');
  process.env.METALLIKSA_JOB_ROOT = jobRoot;
  process.env.WSLENV = [...forwarded, 'METALLIKSA_JOB_ROOT/p'].join(':');
  return () => {
    restoreEnv('METALLIKSA_JOB_ROOT', prior.jobRoot);
    restoreEnv('WSLENV', prior.wslenv);
  };
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
