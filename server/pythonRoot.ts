import { existsSync } from 'node:fs';
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

/**
 * Start-up layout check. Returns an error message when the working directory is not an application
 * root: python/persistent_ipc_service.py is always required, dist/index.html in production.
 */
export function startupLayoutError(cwd: string, production: boolean, exists: (file: string) => boolean = existsSync): string | null {
  const required = [path.join(resolvePythonRoot(cwd), 'persistent_ipc_service.py')];
  if (production) required.push(path.resolve(cwd, 'dist', 'index.html'));
  const missing = required.filter((file) => !exists(file));
  if (missing.length === 0) return null;
  return `Start the server from the application root (the directory with python/${production ? ' and the dist/ built by `npm run build`' : ''}). `
    + `Working directory: ${cwd}. Missing: ${missing.join(', ')}.`;
}
