import { pythonStatusResponse } from "../server/pythonStatus.ts";
import { Router, Request, Response } from "express";
import { runPythonScript, pythonIPCSupervisor } from "../server/processOrchestrator.ts";
import { parsePythonStdout, pythonDispatchStatus } from "../server/pythonDispatchStatus.ts";

export const physicsRouter = Router();

// Overridable runner so route tests can exercise the status mapping without spawning Python.
export const physicsDeps = { runPythonScript };

async function handlePythonDispatch(scriptPath: string, payload: any, res: Response, timeoutMs: number = 25000) {
  try {
    const pyRes = await physicsDeps.runPythonScript(scriptPath, payload, [], timeoutMs);
    if (!pyRes.stdout && pyRes.stderr) {
      console.warn(`[Python stderr: ${scriptPath}]`, pyRes.stderr);
    }
    const stdout = (pyRes.stdout || "").trim();
    if (!stdout) {
      return res.status(500).json({
        error: pyRes.stderr?.trim() || `Python ${scriptPath} returned empty stdout (exit ${pyRes.exitCode}).`,
        script: scriptPath,
        stderr: pyRes.stderr,
      });
    }
    const parsed: any = parsePythonStdout(stdout) ?? { rawOutput: pyRes.stdout, stderr: pyRes.stderr, durationMs: pyRes.durationMs };
    return res.status(pythonDispatchStatus(parsed)).json(parsed);
  } catch (err: any) {
    console.error(`[Python error: ${scriptPath}]`, err);
    return res.status(500).json({
      error: err.message || "Failed to execute Python computation",
      script: scriptPath,
    });
  }
}

// System status & IPC health
physicsRouter.get("/api/python/status", (_req: Request, res: Response) => {
  const ipc = pythonIPCSupervisor.getStatus();
  res.json(pythonStatusResponse(ipc, process.platform));
});

physicsRouter.get("/api/python/ipc-status", (_req: Request, res: Response) => {
  res.json(pythonIPCSupervisor.getStatus());
});

physicsRouter.post("/api/python/ipc-warmup", async (_req: Request, res: Response) => {
  const ipc = pythonIPCSupervisor.getStatus();
  const ready = ipc.status === "online";
  res.status(ready ? 200 : 503).json({ success: ready, status: ipc.status, message: ready ? "Python IPC daemon ready" : "Python IPC daemon is not ready" });
});

// CALPHAD Gibbs Minimization & Databases
physicsRouter.post(["/api/python/calphad-minimize", "/api/calphad/minimize"], (req: Request, res: Response) => {
  return handlePythonDispatch("python/calphad_solver.py", req.body, res, 240000);
});

physicsRouter.get(["/api/python/calphad-databases", "/api/calphad/databases"], (req: Request, res: Response) => {
  return handlePythonDispatch("python/calphad_solver.py", { action: "list_databases" }, res, 15000);
});

// LPBF 3D Thermal Solver
physicsRouter.post("/api/python/lpbf-thermal-solver", (req: Request, res: Response) => {
  return handlePythonDispatch("python/lpbf_thermal_solver.py", req.body, res);
});

physicsRouter.post("/api/python/stl-slicer-build-time", (req: Request, res: Response) => {
  return handlePythonDispatch("python/stl_slicer_build_time_solver.py", req.body, res);
});



// Phase 6: Bayesian Process Window Optimization
physicsRouter.post("/api/python/lpbf-bayesian-optimize", (req: Request, res: Response) => {
  return handlePythonDispatch("python/lpbf_bayesian_optimizer.py", req.body, res, 120000);
});

// Opt-in calibrated melt-pool mode (screening only, not validation): the frozen solver run with a fitted
// effective absorptivity for gate-enabled cells only. A NEW route; /api/python/lpbf-thermal-solver is untouched.
physicsRouter.post("/api/python/lpbf-calibrated-meltpool", (req: Request, res: Response) => {
  return handlePythonDispatch("python/lpbf_calibrated_meltpool.py", req.body, res);
});

// LPBF process-window map (screening only, not validation): P x v grid of the frozen screening verdict plus a
// published-measurement overlay. 11 x 11 default grid at about 20 ms per cell, plus one model verdict per overlay
// point. A NEW route appended at the end of this file; no existing route or line reference moves.
physicsRouter.post("/api/python/lpbf-process-window", (req: Request, res: Response) => {
  return handlePythonDispatch("python/lpbf_process_window.py", req.body, res, 60000);
});
