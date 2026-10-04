// Display text for the ICME pipeline's numbers that can be unavailable (python/icme_multiscale_pipeline_solver.py).
// UTS, K_Ic, the critical flaw size and the plastic zone radius are null (with a *_status reason) because the
// illustrative model has no valid way to compute them. A null/missing/non-finite value is shown as "Unavailable",
// never as 0, NaN or an invented number.
export const ICME_UNAVAILABLE_TEXT = "Unavailable";

export const formatOptionalValue = (value: number | null | undefined, unit: string): string =>
  typeof value === "number" && Number.isFinite(value) ? `${value} ${unit}` : ICME_UNAVAILABLE_TEXT;
