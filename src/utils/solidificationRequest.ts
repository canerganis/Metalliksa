export interface LatestRequestGate {
  begin(): number;
  invalidate(): void;
  isCurrent(generation: number): boolean;
}

export function createLatestRequestGate(): LatestRequestGate {
  let generation = 0;
  return {
    begin: () => ++generation,
    invalidate: () => { generation += 1; },
    isCurrent: (candidate) => candidate === generation,
  };
}

export async function settleLatestRequest<T>(
  gate: LatestRequestGate,
  generation: number,
  request: () => Promise<T>,
  handlers: {
    onSuccess: (value: T) => void;
    onError: (error: unknown) => void;
    onFinally: () => void;
  },
): Promise<void> {
  try {
    const value = await request();
    if (gate.isCurrent(generation)) handlers.onSuccess(value);
  } catch (error) {
    if (gate.isCurrent(generation)) handlers.onError(error);
  } finally {
    if (gate.isCurrent(generation)) handlers.onFinally();
  }
}
