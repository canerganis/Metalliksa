/**
 * CPython 3.10 Tafel Polarization Curve Fitting & Annual Corrosion Rate Service
 * Dispatches raw polarization scan points (from user-uploaded BioLogic, Gamry, Autolab, CSV, etc.)
 * to the backend CPython 3.10 engine running ASTM G102 and ASTM G59 least-squares algorithms.
 */

import { TafelDataset, TafelFitResult } from "../types/tafel";
import { tryAutoFitTafel } from "./tafelParser";
import { isPythonValidationError, validationErrorFromResponse } from "./pythonValidationError";

export interface PythonFitOptions {
  customCathodicRange?: [number, number];
  customAnodicRange?: [number, number];
  manualEcorrOverride?: number;
  manualIcorrOverride?: number;
  alloyId?: string;
}

/** A finite number or null: the engine reports unavailable values as null, and Number(null) would turn them into 0. */
const finiteOrNull = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** A required numeric pair (fit window / valley) from the response; a missing one is a malformed response. */
function requireRange(v: unknown, name: string): [number, number] {
  if (Array.isArray(v) && v.length === 2 && finiteOrNull(v[0]) !== null && finiteOrNull(v[1]) !== null) {
    return [v[0], v[1]];
  }
  throw new Error(`Python Tafel response has no valid ${name}`);
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

    // Every value the engine reports as null is unavailable and stays null (no 0, no default slope or R2).
    const refOffset = dataset.metadata.refOffsetVsSHE ?? 0.241;
    const eCorr = finiteOrNull(data.eCorr);
    const eCorrSHE = eCorr === null ? null : Number((eCorr + refOffset).toFixed(4));
    const iCorr_uA_cm2 = finiteOrNull(data.iCorr_uA_cm2);
    const logIcorr = finiteOrNull(data.logIcorr);
    const totalCurrentIcorr_uA =
      iCorr_uA_cm2 === null ? null : Number((iCorr_uA_cm2 * (dataset.metadata.electrodeAreaCm2 || 1.0)).toFixed(4));

    // Map the corrosion rate to the severity union (null without a rate)
    let severity: TafelFitResult["severity"] = null;
    const sevObj = data.severity;
    const crMm = finiteOrNull(data.corrosionRateMmYr);
    if (crMm !== null) {
      if (crMm < 0.02) {
        severity = "Immune / Highly Resistant";
      } else if (crMm < 0.1) {
        severity = "Passivated / Good";
      } else if (crMm < 0.5) {
        severity = "Moderate (Caution)";
      } else {
        severity = "Severe Rapid Corrosion";
      }
    }

    const rawEcorrValley = finiteOrNull(data.rawEcorrValley);
    const rawIcorrValley = finiteOrNull(data.rawIcorrValley);
    if (rawEcorrValley === null || rawIcorrValley === null) {
      throw new Error("Python Tafel response has no measured current valley");
    }

    const fitResult: TafelFitResult = {
      eCorr,
      eCorrSHE,
      iCorr_uA_cm2,
      logIcorr,
      totalCurrentIcorr_uA,
      betaA_V_dec: finiteOrNull(data.betaA_V_dec),
      betaA_mV_dec: finiteOrNull(data.betaA_mV_dec),
      betaC_V_dec: finiteOrNull(data.betaC_V_dec),
      betaC_mV_dec: finiteOrNull(data.betaC_mV_dec),
      sternGearyB_V: finiteOrNull(data.sternGearyB_V),
      rp_ohm_cm2: finiteOrNull(data.rp_ohm_cm2),
      corrosionRateMmYr: crMm,
      corrosionRateMpy: finiteOrNull(data.corrosionRateMpy),
      massLoss_g_m2_day: finiteOrNull(data.massLoss_g_m2_day),
      cathodicRange: requireRange(data.cathodicRange, "cathodic fit window"),
      anodicRange: requireRange(data.anodicRange, "anodic fit window"),
      cathodicR2: finiteOrNull(data.cathodicR2),
      anodicR2: finiteOrNull(data.anodicR2),
      cathodicSlope_m: finiteOrNull(data.cathodicSlope_dLogI_dE),
      cathodicIntercept_b: null, // the engine does not return the intercepts
      anodicSlope_m: finiteOrNull(data.anodicSlope_dLogI_dE),
      anodicIntercept_b: null,
      rawEcorrValley,
      rawIcorrValley,
      tangentLines: data.tangentLines || [],
      syntheticButlerVolmer: data.syntheticButlerVolmer || [],
      severity,
      astmClassification:
        sevObj && typeof sevObj === "object" ? `${sevObj.level} (${sevObj.description})` : null,
      isPythonEngine: true,
      pythonVersion: data.pythonVersion || "3.10.x",
      durationMs: data.durationMs || 0,
      ...(data.fitStatus === "unavailable"
        ? {
            fitStatus: "unavailable" as const,
            unavailable: data.unavailable && typeof data.unavailable === "object" ? data.unavailable : undefined,
            unavailableReason: typeof data.unavailableReason === "string" ? data.unavailableReason : undefined,
          }
        : {}),
    };

    return fitResult;
  } catch (err) {
    // Invalid input (e.g. unknown alloy): surface it, never substitute the client fit.
    if (isPythonValidationError(err)) throw err;
    console.warn("Python Tafel engine call failed, running local browser fallback:", err);
    // Graceful fallback to client-side ASTM mathematical engine
    const local = tryAutoFitTafel(
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
