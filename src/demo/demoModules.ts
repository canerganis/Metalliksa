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
];

export function isDemoModule(id: string): boolean {
  return DEMO_MODULES.includes(id);
}

/**
 * Panel boundaries inside the shown modules (docs/DEMO_STATIC_DESIGN.md section 5). `shown` panels render
 * recorded output; `unavailable` panels render the "Not available in the static demo." note instead.
 * 3d-distortion-lab ids are workflow stage ids plus "specialists" (the Melt pool 3D specialist lab);
 * lpbf-optimizer ids are its tab ids.
 */
export const DEMO_PANELS: Readonly<Record<string, { readonly shown: readonly string[]; readonly unavailable: readonly string[] }>> = {
  '3d-distortion-lab': {
    shown: ['setup', 'material', 'thermal', 'melt-pool', 'qualification'],
    unavailable: ['defects', 'build', 'comparison', 'specialists'],
  },
  'lpbf-optimizer': { shown: ['window'], unavailable: ['search', 'plan'] },
};

/** True when the panel is rendered in the demo. Unknown modules and panels are not shown. */
export function isDemoPanelShown(moduleId: string, panelId: string): boolean {
  return DEMO_PANELS[moduleId]?.shown.includes(panelId) ?? false;
}
