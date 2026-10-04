import path from 'node:path';

/**
 * Absolute path of the application's python/ directory.
 *
 * Anchored on the working directory, like the persistent IPC worker
 * (server/processOrchestrator.ts: <cwd>/python/persistent_ipc_service.py) and the production
 * static root (server.ts: <cwd>/dist). The server is started from the application root: the
 * repository root for `npm run dev` / `npm start`, /app in the Docker runtime image.
 *
 * Do not derive this from import.meta.url: `npm run build` bundles the server with
 * `esbuild --format=cjs`, which replaces import.meta with an empty object, so
 * fileURLToPath(import.meta.url) throws while dist/server.cjs is loading.
 */
export function resolvePythonRoot(cwd: string = process.cwd()): string {
  return path.resolve(cwd, 'python');
}
