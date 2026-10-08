import { Router, Request, Response } from "express";
import { runPythonScript } from "../server/processOrchestrator.ts";
import { parsePythonStdout, pythonDispatchStatus } from "../server/pythonDispatchStatus.ts";

export const characterizationRouter = Router();

// Overridable runner so route tests can exercise validation without spawning Python.
export const characterizationDeps = { runPythonScript };

async function handlePythonDispatch(scriptPath: string, payload: any, res: Response) {
  try {
    const pyRes = await characterizationDeps.runPythonScript(scriptPath, payload);
    if (!pyRes.stdout && pyRes.stderr) {
      console.warn(`[Python stderr: ${scriptPath}]`, pyRes.stderr);
    }
    const parsed: any = parsePythonStdout(pyRes.stdout || "{}") ?? { rawOutput: pyRes.stdout, stderr: pyRes.stderr, durationMs: pyRes.durationMs };
    return res.status(pythonDispatchStatus(parsed)).json(parsed);
  } catch (err: any) {
    console.error(`[Python error: ${scriptPath}]`, err);
    return res.status(500).json({
      error: err.message || "Failed to execute Python characterization computation",
      script: scriptPath,
    });
  }
}

// XRD Peak Deconvolution & Rietveld
characterizationRouter.post("/api/python/xrd-deconvolve", (req: Request, res: Response) => {
  return handlePythonDispatch("python/xrd_peak_deconvolution.py", req.body, res);
});
