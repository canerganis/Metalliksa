import express, { Request, Response, NextFunction } from "express";
import path from "path";
import dotenv from "dotenv";
import { createServer } from "node:http";
import { attachDevelopmentMiddleware } from "./server/devMiddleware.ts";

import { physicsRouter } from "./routes/physics.ts";
import { lpbfSimulationRouter } from "./routes/lpbfSimulation.ts";
import { characterizationRouter } from "./routes/characterization.ts";
import { copilotRouter } from "./routes/copilot.ts";
import { researchRouter } from "./routes/research.ts";
import { orchestratorRouter } from "./routes/orchestrator.ts";
import { createResearchRegistryRouter } from "./routes/researchRegistry.ts";
import { createLpbfSourcesRouter } from "./routes/lpbfSources.ts";
import { createLpbfRunsRouter } from "./routes/lpbfRuns.ts";
import { processOrchestrationMiddleware } from "./server/processOrchestrator.ts";
import {
  AIRGAP_ALLOWED_LOCAL,
  AIRGAP_BLOCKED_SERVICES,
  isAirgappedFromEnv,
} from "./server/airgap.ts";

dotenv.config();

const AIRGAPPED = isAirgappedFromEnv(process.env);

// Process-level crash guards: isolate unhandled rejections and errors
// Ensures an unhandled prompt error or JSON failure in AI copilot cannot terminate the process or affect CALPHAD/EIS
process.on("unhandledRejection", (reason: any) => {
  console.error("[ProcessGuard] Unhandled Promise Rejection intercepted:", reason?.stack || reason);
});

process.on("uncaughtException", (error: Error) => {
  console.error("[ProcessGuard] Uncaught Exception intercepted:", error?.stack || error);
});

const app = express();
const configuredPort = Number(process.env.PORT ?? 3000);
const PORT = Number.isInteger(configuredPort) && configuredPort >= 1 && configuredPort <= 65535 ? configuredPort : 3000;

// Registry payloads have a smaller limit and must run before the global parser.
app.use(createResearchRegistryRouter());
app.use(createLpbfSourcesRouter());
app.use(createLpbfRunsRouter());

// Body parsing with generous payload capacity for base64 micrograph scans & CAD models
app.use(express.json({ limit: "50mb" }));
app.use(express.urlencoded({ extended: true, limit: "50mb" }));

// Process orchestration & subprocess telemetry middleware
app.use(processOrchestrationMiddleware);

// Server & Infrastructure Health Endpoint
app.get("/api/health", (_req: Request, res: Response) => {
  res.json({
    status: "ok",
    service: "MetalliX-Unified-Server",
    hasApiKey: AIRGAPPED ? false : !!process.env.OPENAI_API_KEY?.trim(),
    airgapped: AIRGAPPED,
    timestamp: new Date().toISOString(),
  });
});

app.get("/api/runtime-config", (_req: Request, res: Response) => {
  res.json({
    airgapped: AIRGAPPED,
    blockedServices: AIRGAPPED ? AIRGAP_BLOCKED_SERVICES : [],
    allowedLocal: [...AIRGAP_ALLOWED_LOCAL],
  });
});

// =========================================================================
// Modular Express Controllers
// =========================================================================
// 1. HPC Physics & Computational Metallurgy (CALPHAD, DFT, LPBF, Kinetics, ICME, UQ)
app.use(physicsRouter);
app.use(lpbfSimulationRouter);

// 2. Experimental Characterization & Spectroscopy (EIS, XRD, Battery Degradation, SEM Vision)
app.use(characterizationRouter);

// 3. AI Copilot, Metallurgy Consultation, Alloy Formulation & Materials Project
app.use(copilotRouter);
app.use(researchRouter);
app.use(orchestratorRouter);

// Explicit JSON 404 for unmatched /api routes (prevents SPA index.html fallback for API calls)
app.all("/api/*", (req: Request, res: Response) => {
  res.status(404).json({
    error: `API endpoint ${req.method} ${req.originalUrl} not found`,
  });
});

// Global Process-Isolated Error Handling Middleware
// Prevents unhandled JSON parsing errors or route exceptions from terminating the Node server process
app.use((err: any, _req: Request, res: Response, _next: NextFunction) => {
  console.error("[ServerError] Unhandled Express pipeline error:", err?.stack || err);
  res.status(err.status || 500).json({
    error: err.message || "An internal server error occurred.",
    code: err.code || "INTERNAL_SERVER_ERROR",
  });
});

// =========================================================================
// Vite Middleware & SPA Serving Pipeline
// =========================================================================
async function startServer() {
  const httpServer = createServer(app);
  if (process.env.NODE_ENV !== "production") {
    await attachDevelopmentMiddleware(app, httpServer);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (_req: Request, res: Response) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  httpServer.listen(PORT, "0.0.0.0", () => {
    console.log(`[MetalliX-Server] Modular server running on http://localhost:${PORT}`);
    if (AIRGAPPED) {
      console.log("[MetalliX-Server] AIRGAPPED=1 — GPT-6 / NVIDIA / live MP / external pricing disabled; local LPBF open.");
    }
  });
}

startServer();
