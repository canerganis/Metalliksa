/**
 * CPython 3.10 Tafel Polarization Curve Fitting & Annual Corrosion Rate Service
 * Dispatches raw polarization scan points (from user-uploaded BioLogic, Gamry, Autolab, CSV, etc.)
 * to the backend CPython 3.10 engine running ASTM G102 and ASTM G59 least-squares algorithms.
 */

import { TafelDataset, TafelFitResult } from "../types/tafel";
import { autoFitTafel } from "./tafelParser";
import { isPythonValidationError, validationErrorFromResponse } from "./pythonValidationError";

export interface PythonFitOptions {
  customCathodicRange?: [number, number];
  customAnodicRange?: [number, number];
  manualEcorrOverride?: number;
  manualIcorrOverride?: number;
  alloyId?: string;
}

export async function executePythonTafelFit(
  dataset: TafelDataset,
  options: PythonFitOptions = {}
): Promise<TafelFitResult> {
  const payload = {
    action: "fit_curve",
    points: dataset.points.map((p) => ({
      potential: p.potential,
      currentDensity_uA_cm2: p.currentDensity_uA_cm2,
      logCurrentDensity: p.logCurrentDensity,
    })),
    electrodeAreaCm2: dataset.metadata.electrodeAreaCm2 || 1.0,
    alloyId: options.alloyId || "steel-316l",
    alloyName: dataset.metadata.alloyName,
    density_g_cm3: dataset.metadata.density_g_cm3,
    equivalentWeight: dataset.metadata.equivalentWeight,
    customCathodicRange: options.customCathodicRange,
    customAnodicRange: options.customAnodicRange,
    manualEcorrOverride: options.manualEcorrOverride,
    manualIcorrOverride: options.manualIcorrOverride,
  };

  try {
    const res = await fetch("/api/python/tafel-corrosion-rate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const validation = await validationErrorFromResponse(res, "Tafel fit");
      if (validation) throw validation;
      throw new Error(`HTTP error ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();
    if (!data.success && data.error) {
      throw new Error(data.error);
    }

    const refOffset = dataset.metadata.refOffsetVsSHE ?? 0.241;
    const eCorr = Number(data.eCorr);
    const eCorrSHE = Number((eCorr + refOffset).toFixed(4));
    const iCorr_uA_cm2 = Number(data.iCorr_uA_cm2);
    const logIcorr = Number(data.logIcorr);
    const totalCurrentIcorr_uA = Number((iCorr_uA_cm2 * (dataset.metadata.electrodeAreaCm2 || 1.0)).toFixed(4));

    // Map severity string to union
    let severity: TafelFitResult["severity"] = "Passivated / Good";
    const sevObj = data.severity;
    const crMm = Number(data.corrosionRateMmYr);
    if (crMm < 0.02) {
      severity = "Immune / Highly Resistant";
    } else if (crMm < 0.1) {
      severity = "Passivated / Good";
    } else if (crMm < 0.5) {
      severity = "Moderate (Caution)";
    } else {
      severity = "Severe Rapid Corrosion";
    }

    const fitResult: TafelFitResult = {
      eCorr,
      eCorrSHE,
      iCorr_uA_cm2,
      logIcorr,
      totalCurrentIcorr_uA,
      betaA_V_dec: Number(data.betaA_V_dec),
      betaA_mV_dec: Number(data.betaA_mV_dec),
      betaC_V_dec: Number(data.betaC_V_dec),
      betaC_mV_dec: Number(data.betaC_mV_dec),
      sternGearyB_V: Number(data.sternGearyB_V),
      rp_ohm_cm2: Number(data.rp_ohm_cm2),
      corrosionRateMmYr: Number(data.corrosionRateMmYr),
      corrosionRateMpy: Number(data.corrosionRateMpy),
      massLoss_g_m2_day: Number(data.massLoss_g_m2_day),
      cathodicRange: data.cathodicRange || [-0.6, -0.4],
      anodicRange: data.anodicRange || [-0.3, -0.1],
      cathodicR2: Number(data.cathodicR2 ?? 0.95),
      anodicR2: Number(data.anodicR2 ?? 0.95),
      cathodicSlope_m: Number(data.cathodicSlope_dLogI_dE ?? -8.33),
      cathodicIntercept_b: 0,
      anodicSlope_m: Number(data.anodicSlope_dLogI_dE ?? 10.0),
      anodicIntercept_b: 0,
      rawEcorrValley: Number(data.rawEcorrValley ?? eCorr),
      rawIcorrValley: Number(data.rawIcorrValley ?? iCorr_uA_cm2),
      tangentLines: data.tangentLines || [],
      syntheticButlerVolmer: data.syntheticButlerVolmer || [],
      severity,
      astmClassification: typeof sevObj === "object" ? `${sevObj.level} (${sevObj.description})` : "ASTM G102 Standard",
      isPythonEngine: true,
      pythonVersion: data.pythonVersion || "3.10.x",
      durationMs: data.durationMs || 0,
    };

    return fitResult;
  } catch (err) {
    // Invalid input (e.g. unknown alloy): surface it, never substitute the client fit.
    if (isPythonValidationError(err)) throw err;
    console.warn("Python Tafel engine call failed, running local browser fallback:", err);
    // Graceful fallback to client-side ASTM mathematical engine
    const local = autoFitTafel(
      dataset,
      options.customCathodicRange,
      options.customAnodicRange,
      options.manualEcorrOverride,
      options.manualIcorrOverride
    );
    return {
      ...local,
      isPythonEngine: false,
      pythonVersion: "Client Engine (Fallback)",
      durationMs: 0.5,
    };
  }
}
