/**
 * Allowlist of modules shown in the static demo (docs/DEMO_STATIC_DESIGN.md section 5).
 * Everything else is hidden. The navigation, command palette and hash resolver filtering is WP3;
 * WP1 only owns the list. The home page is not a module id and is always reachable.
 */
export const DEMO_MODULES: readonly string[] = [
  '3d-distortion-lab',
  'lpbf-optimizer',
  'lpbf-dataset-comparison',
  'lpbf-calibration-scorecard',
  'keyhole-raytracing',
];

export function isDemoModule(id: string): boolean {
  return DEMO_MODULES.includes(id);
}
