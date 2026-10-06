import type { Express } from 'express';
import type { Server } from 'node:http';
import { createServer } from 'vite';

export async function attachDevelopmentMiddleware(app: Express, httpServer: Server) {
  const disableHmr = process.env.DISABLE_HMR === 'true';
  const vite = await createServer({
    server: {
      middlewareMode: true,
      // Reuse this instance's HTTP listener instead of a shared port 24678.
      hmr: disableHmr ? false : { server: httpServer },
      // Vite's hmr:false alone still creates its websocket transport.
      ws: disableHmr ? false : undefined,
    },
    appType: 'spa',
  });
  app.use(vite.middlewares);
  return vite;
}
