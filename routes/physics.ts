import { pythonStatusResponse } from "../server/pythonStatus.ts";
import { Router, Request, Response } from "express";
import { runPythonScript, pythonIPCSupervisor } from "../server/processOrchestrator.ts";
import { pythonDispatchStatus } from "../server/pythonDispatchStatus.ts";

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
    let parsed: any;
    try {
      parsed = JSON.parse(stdout);
    } catch {
      parsed = { rawOutput: pyRes.stdout, stderr: pyRes.stderr, durationMs: pyRes.durationMs };
    }
    return res.status(pythonDispatchStatus(parsed, pyRes.exitCode)).json(parsed);
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
  return handlePythonDispatch("python/calphad_solver.py", req.body, res, 40000);
});

physicsRouter.get(["/api/python/calphad-databases", "/api/calphad/databases"], (req: Request, res: Response) => {
  return handlePythonDispatch("python/calphad_solver.py", { action: "list_databases" }, res, 15000);
});

// DFT Properties
physicsRouter.post("/api/python/dft-properties", (req: Request, res: Response) => {
  return handlePythonDispatch("python/dft_property_calculator.py", req.body, res);
});

// LPBF 3D Thermal Solvers
physicsRouter.post("/api/python/lpbf-thermal", (req: Request, res: Response) => {
  return handlePythonDispatch("python/lpbf_thermal_solver.py", req.body, res);
});

physicsRouter.post("/api/python/lpbf-thermal-solver", (req: Request, res: Response) => {
  return handlePythonDispatch("python/lpbf_thermal_solver.py", req.body, res);
});

physicsRouter.post("/api/python/marangoni-pore-instability", (req: Request, res: Response) => {
  return handlePythonDispatch("python/marangoni_pore_instability_solver.py", req.body, res);
});

physicsRouter.post("/api/python/stl-slicer-build-time", (req: Request, res: Response) => {
  return handlePythonDispatch("python/stl_slicer_build_time_solver.py", req.body, res);
});



// Phase 6: Bayesian Process Window Optimization
physicsRouter.post("/api/python/lpbf-bayesian-optimize", (req: Request, res: Response) => {
  return handlePythonDispatch("python/lpbf_bayesian_optimizer.py", req.body, res, 120000);
});

physicsRouter.post("/api/python/part-scale-inherent-strain", (req: Request, res: Response) => {
  return handlePythonDispatch("python/part_scale_inherent_strain_solver.py", req.body, res);
});

// Inverse Alloy Optimizer
physicsRouter.post("/api/python/inverse-alloy-optimize", (req: Request, res: Response) => {
  return handlePythonDispatch("python/inverse_alloy_optimizer.py", req.body, res);
});

// Pourbaix Diagram
physicsRouter.post("/api/python/pourbaix-diagram", (req: Request, res: Response) => {
  return handlePythonDispatch("python/pourbaix_solver.py", req.body, res);
});

// Kinetics TTT / CCT
physicsRouter.post("/api/python/kinetics-ttt-cct", (req: Request, res: Response) => {
  return handlePythonDispatch("python/kinetics_ttt_cct_solver.py", req.body, res);
});

// ICME Multiscale
physicsRouter.post("/api/python/icme-multiscale-pipeline", (req: Request, res: Response) => {
  return handlePythonDispatch("python/icme_multiscale_pipeline_solver.py", req.body, res);
});

// Stochastic UQ MMPDS
physicsRouter.post("/api/python/stochastic-uq-mmpds", (req: Request, res: Response) => {
  return handlePythonDispatch("python/stochastic_uq_mmpds_solver.py", req.body, res);
});
