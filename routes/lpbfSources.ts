import express, { Router, type ErrorRequestHandler, type RequestHandler } from 'express';
import { LpbfSourceArchiveError, LpbfSourceArchiveService } from '../server/lpbfSourceArchiveService';

/** Must precede the global large-body parser. Client paths/URLs/documents are not accepted. */
export function createLpbfSourcesRouter(service = new LpbfSourceArchiveService()): Router {
  const router = Router();
  const prefix = '/api/lpbf/sources';
  router.use(prefix, (req, res, next) => {
    res.set('Cache-Control', 'no-store');
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
      if (process.env.METALLIKSA_READ_ONLY === 'true') {
        res.status(403).json({ error: 'Application is in read-only mode. Write operations are disabled.' }); return;
      }
      const origin = req.get('origin');
      if (req.get('sec-fetch-site') === 'cross-site' || (origin !== undefined && origin !== `${req.protocol}://${req.get('host')}`)) {
        res.status(403).json({ error: 'Source archive requests must originate from this application.' }); return;
      }
      if (!req.is('application/json')) { res.status(415).json({ error: 'Source archive requests require application/json.' }); return; }
    }
    next();
  }, express.json({ limit: '16kb', strict: true }));

  const handle = (action: (req: express.Request) => unknown | Promise<unknown>): RequestHandler => async (req, res) => {
    try { res.json(await action(req)); }
    catch (error) {
      if (error instanceof LpbfSourceArchiveError) { res.status(error.status).json({ error: error.message }); return; }
      console.error('[LPBF source archive]', error);
      res.status(503).json({ error: 'Source archive unavailable or integrity check failed. Existing revisions were preserved.' });
    }
  };
  function body(req: express.Request, keys: string[]) {
    if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)
      || Object.keys(req.body).length !== keys.length || keys.some(key => !Object.hasOwn(req.body, key))) {
      throw new LpbfSourceArchiveError(400, 'Unexpected source archive request fields.');
    }
  }
  const decimalInteger = (value: unknown, fallback: number) => value === undefined ? fallback
    : typeof value === 'string' && /^(0|[1-9]\d*)$/.test(value) ? Number(value) : Number.NaN;
  router.get(prefix, handle(() => service.catalog()));
  router.get(`${prefix}/:datasetId`, handle(req => service.current(req.params.datasetId)));
  router.get(`${prefix}/:datasetId/revisions`, handle(req => {
    const offset = decimalInteger(req.query.offset, 0);
    const limit = decimalInteger(req.query.limit, 100);
    return service.revisions(req.params.datasetId, offset, limit);
  }));
  router.get(`${prefix}/:datasetId/revisions/:revision`, handle(req =>
    service.revision(req.params.datasetId, decimalInteger(req.params.revision, Number.NaN))));
  router.post(`${prefix}/:datasetId/preview`, handle(req => { body(req, []); return service.preview(req.params.datasetId); }));
  router.post(`${prefix}/:datasetId/import`, handle(req => {
    body(req, ['expectedRevision', 'documentSha256']);
    return service.import(req.params.datasetId, req.body.expectedRevision, req.body.documentSha256);
  }));
  router.post(`${prefix}/:datasetId/verify`, handle(req => { body(req, []); return service.verify(req.params.datasetId); }));
  router.get(`${prefix}/:datasetId/measurements`, handle(req => service.measurements(req.params.datasetId)));
  const bodyError: ErrorRequestHandler = (error, _req, res, _next) => {
    res.status(error?.status === 413 ? 413 : 400).json({ error: error?.status === 413 ? 'Source request exceeds 16 KiB.' : 'Source request must contain valid JSON.' });
  };
  router.use(prefix, bodyError);
  return router;
}
