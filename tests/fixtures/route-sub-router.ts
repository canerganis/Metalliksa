// Fixture for tests/route-authority.test.ts: a sub-router with relative paths, mounted under an
// /api prefix by the importing module, must be discovered under the joined path (p7 re-audit
// follow-up). Not used by the application.
import { Router } from 'express';

export const cannedSubRouter = Router();
cannedSubRouter.post('/canned', (_req, res) => res.json({ qualified: true }));
cannedSubRouter.get('/', (req, res) => res.json({ query: req.query.q }));
export default cannedSubRouter;
