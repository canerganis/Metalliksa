import type {
  SolidificationMicrostructureAvailable,
  SolidificationMicrostructureResult,
} from '../services/pythonComputationService';

export type SolidificationOutcome = { error: string } | { result: SolidificationMicrostructureAvailable };

/**
 * Guard for the Microstructure Lab: only a Python result with status "available" or "screening-fallback" may
 * reach the numeric panels. "unavailable" yields Python's reason; a legacy block without a status (an old
 * worker) is never rendered as available, and a numeric block that lacks finite G/R/PDAS/SDAS is rejected.
 */
export function solidificationOutcome(res: SolidificationMicrostructureResult | null | undefined): SolidificationOutcome {
  const status = (res as { status?: unknown } | null | undefined)?.status;
  if (status === 'unavailable') {
    return { error: (res as { reason?: string }).reason || 'no solidification data' };
  }
  if (status !== 'available' && status !== 'screening-fallback') {
    return { error: 'legacy result without status' };
  }
  const r = res as SolidificationMicrostructureAvailable;
  for (const value of [r.G_K_m, r.R_m_s, r.coolingRate_K_s, r.PDAS_um, r.SDAS_um]) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return { error: 'result carries no finite G/R/cooling/PDAS/SDAS numbers' };
  }
  return { result: r };
}
