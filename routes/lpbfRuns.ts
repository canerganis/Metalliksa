import express, { Router, type ErrorRequestHandler, type RequestHandler } from 'express';
import { pipeline } from 'node:stream/promises';
import { LpbfRunArchiveError, LpbfRunArchiveService } from '../server/lpbfRunArchiveService';
import { LpbfRunBundleService } from '../server/lpbfRunBundleService';
import { LpbfNistComparisonService } from '../server/lpbfNistComparisonService';
import { LpbfNistProxyCampaignService } from '../server/lpbfNistProxyCampaignService';
import { MAX_RUN_BUNDLE_BYTES } from '../server/lpbfRunBundleTar';

export function createLpbfRunsRouter(service = new LpbfRunArchiveService(), bundles = new LpbfRunBundleService(),
  comparison = new LpbfNistComparisonService(), campaigns = new LpbfNistProxyCampaignService()): Router {
  const router = Router();
  const prefix = '/api/lpbf/runs';

  const writeGuard: RequestHandler = (req, res, next) => {
    res.set('Cache-Control', 'no-store');
    if (process.env.METALLIKSA_READ_ONLY === 'true') {
      res.status(403).json({ error: 'Application is in read-only mode. Write operations are disabled.' }); return;
    }
    const origin = req.get('origin');
    if (req.get('sec-fetch-site') === 'cross-site' || (origin !== undefined && origin !== `${req.protocol}://${req.get('host')}`)) {
      res.status(403).json({ error: 'Run archive requests must originate from this application.' }); return;
    }
    next();
  };

  router.get(`${prefix}/bundles/:bundleId/download`, async (req, res) => {
    res.set('Cache-Control', 'no-store');
    try {
      const archive = await bundles.download(req.params.bundleId);
      res.type('application/x-tar').attachment(`metalliksa-lpbf-run-bundle-${req.params.bundleId}.tar`);
      await pipeline(archive, res);
    } catch (error) {
      if (res.headersSent) { res.destroy(error instanceof Error ? error : undefined); return; }
      if (error instanceof LpbfRunArchiveError) { res.status(error.status).json({ error: error.message }); return; }
      res.status(409).json({ error: 'Run bundle could not be prepared for download.' });
    }
  });

  router.post(`${prefix}/bundles/import`, writeGuard, async (req, res) => {
    res.set('Cache-Control', 'no-store');
    if (!req.is('application/x-tar')) { res.status(415).json({ error: 'Portable run bundles require application/x-tar.' }); return; }
    const contentLength = req.get('content-length');
    if (contentLength !== undefined && (!/^\d+$/.test(contentLength) || Number(contentLength) > MAX_RUN_BUNDLE_BYTES)) {
      res.status(413).json({ error: 'Portable run bundle exceeds the 16 GiB archive limit.' }); return;
    }
    try { res.json(await bundles.importPortable(req)); }
    catch (error) {
      if (error instanceof LpbfRunArchiveError) { res.status(error.status).json({ error: error.message }); return; }
      console.error('[LPBF run bundle import]', error);
      res.status(409).json({ error: 'Portable run bundle could not be verified.' });
    }
  });

  router.use(prefix, (req, res, next) => {
    res.set('Cache-Control', 'no-store');
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
      if (process.env.METALLIKSA_READ_ONLY === 'true') {
        res.status(403).json({ error: 'Application is in read-only mode. Write operations are disabled.' }); return;
      }
      const origin = req.get('origin');
      if (req.get('sec-fetch-site') === 'cross-site' || (origin !== undefined && origin !== `${req.protocol}://${req.get('host')}`)) {
        res.status(403).json({ error: 'Run archive requests must originate from this application.' }); return;
      }
      if (!req.is('application/json')) { res.status(415).json({ error: 'Run archive requests require application/json.' }); return; }
    }
    next();
  }, express.json({ limit: '16kb', strict: true }));

  const handle = (action: (req: express.Request) => unknown | Promise<unknown>): RequestHandler => async (req, res) => {
    try { res.json(await action(req)); }
    catch (error) {
      if (error instanceof LpbfRunArchiveError) { res.status(error.status).json({ error: error.message }); return; }
      console.error('[LPBF run archive]', error);
      res.status(503).json({ error: 'Run archive unavailable or integrity check failed.' });
    }
  };

  router.get(prefix, handle(() => service.list()));
  router.get(`${prefix}/proxy-campaigns`, handle(() => campaigns.list()));
  router.get(`${prefix}/bundles/restores/:restoreId/runs`, handle(req => bundles.listRestoredRuns(req.params.restoreId)));
  router.get(`${prefix}/bundles/restores/:restoreId/runs/:runId`, handle(req => bundles.getRestoredRun(req.params.restoreId, req.params.runId)));
  router.get(`${prefix}/:runId`, handle(req => service.getVerified(req.params.runId)));

  const emptyBody = (req: express.Request) => {
    if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body) || Object.keys(req.body).length) {
      throw new LpbfRunArchiveError(400, 'Bundle request body must be an empty object.');
    }
  };
  router.post(`${prefix}/bundles/export`, handle(req => { emptyBody(req); return bundles.export(); }));
  router.post(`${prefix}/bundles/:bundleId/verify`, handle(req => { emptyBody(req); return bundles.verify(req.params.bundleId); }));
  router.post(`${prefix}/bundles/:bundleId/restore`, handle(req => { emptyBody(req); return bundles.restore(req.params.bundleId); }));
  router.post(`${prefix}/bundles/imports/:bundleId/restore`, handle(req => { emptyBody(req); return bundles.restoreImported(req.params.bundleId); }));
  const comparisonCaseNumber = (req: express.Request): string => {
    if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)
      || Object.keys(req.body).length !== 1 || typeof req.body.caseNumber !== 'string') {
      throw new LpbfRunArchiveError(400, 'Only a Table 4 caseNumber is accepted.');
    }
    return req.body.caseNumber;
  };
  router.post(`${prefix}/bundles/restores/:restoreId/runs/:runId/nist-comparison`, handle(async req => {
    const caseNumber = comparisonCaseNumber(req);
    const { runRoot, sourceRoot } = await bundles.restoredComparisonRoots(req.params.restoreId);
    return new LpbfNistComparisonService(runRoot, sourceRoot).compare(req.params.runId, caseNumber);
  }));
  router.post(`${prefix}/:runId/nist-comparison`, handle(req => {
    return comparison.compare(req.params.runId, comparisonCaseNumber(req));
  }));

  router.post(`${prefix}/proxy-campaigns/preview`, handle(req => {
    if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)
      || Object.keys(req.body).sort().join() !== 'caseNumber,runIds') {
      throw new LpbfRunArchiveError(400, 'Proxy campaign preview accepts only runIds and caseNumber.');
    }
    return campaigns.preview(req.body.runIds, req.body.caseNumber);
  }));
  router.post(`${prefix}/proxy-campaigns`, handle(req => {
    if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)
      || Object.keys(req.body).sort().join() !== 'caseNumber,previewSha256,runIds') {
      throw new LpbfRunArchiveError(400, 'Proxy campaign creation requires runIds, caseNumber and previewSha256.');
    }
    return campaigns.create(req.body.runIds, req.body.caseNumber, req.body.previewSha256);
  }));
  
  router.post(`${prefix}/preview`, handle(req => {
    if (!req.body || typeof req.body.jobId !== 'string' || !Array.isArray(req.body.sources)) {
      throw new LpbfRunArchiveError(400, 'jobId and sources array are required.');
    }
    return service.preview(req.body.jobId, req.body.sources);
  }));

  router.post(`${prefix}/import`, handle(req => {
    if (!req.body || typeof req.body.jobId !== 'string' || !Array.isArray(req.body.sources)) {
      throw new LpbfRunArchiveError(400, 'jobId and sources array are required.');
    }
    return service.import(req.body.jobId, req.body.sources);
  }));

  const bodyError: ErrorRequestHandler = (error, _req, res, _next) => {
    res.status(error?.status === 413 ? 413 : 400).json({ error: error?.status === 413 ? 'Run request exceeds 16 KiB.' : 'Run request must contain valid JSON.' });
  };
  router.use(prefix, bodyError);
  
  return router;
}
