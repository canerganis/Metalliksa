// Fixture for tests/route-authority.test.ts: literals moved into an imported module must still
// be recognised as canned results (review fix round 2, item 4). Not used by the application.
export const CANNED_RESULT = { qualified: true, safetyMarginPct: 18.5 };
export const CANNED_LIMIT = 16 * 1024;
export function cannedHelper() {
  return { grainSizeUm: 14.8 };
}
// Helper object methods (`H.make()`) and a default export alias (p7 re-audit follow-up).
export const CANNED_HELPERS = {
  make: () => ({ qualified: true }),
  build() {
    return { porosityPct: 0.042 };
  },
};
const cannedDefault = () => ({ confidence: 0.94 });
export default cannedDefault;
