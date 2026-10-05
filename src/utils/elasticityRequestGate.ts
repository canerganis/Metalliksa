/** Distinguishes successive requests even when their input values are identical. */
export function createElasticityRequestGate() {
  let generation = 0;
  return {
    begin: () => ++generation,
    invalidate: () => { generation++; },
    isCurrent: (request: number) => request === generation,
  };
}
