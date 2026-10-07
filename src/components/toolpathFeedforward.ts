/** Pure helpers of the Feed-forward power tab of the Scan Path Kinematics module (moved from the former Corner Power Compensation view). */

export const SAMPLE_FEEDFORWARD_GCODE = `; LPBF short-vector test pattern (vectors too short to reach the commanded speed)
G0 X0.0 Y0.0
M3 S280
G1 X15.0 Y0.0 F60000
G1 X15.0 Y0.15 F60000
G1 X0.0 Y0.15 F60000
G1 X0.0 Y0.3 F60000
G1 X15.0 Y0.3 F60000
M5
G0 X0.0 Y0.0
`;

/** Rotation the engine applies: 67° × layer index when enabled, else 0. */
export function rotationPreviewDeg(enabled: boolean, layerIndex: number): number {
  return enabled ? Math.round(67 * layerIndex * 10) / 10 : 0;
}

/** Text for the rotation preview under the layer index control. */
export function rotationPreviewText(enabled: boolean, layerIndex: number): string {
  if (!enabled) return 'Rotation disabled (0°)';
  return `Rotation applied = 67° × ${layerIndex} = ${rotationPreviewDeg(true, layerIndex)}°`;
}

/** Signed text for the total commanded energy change (engine reports a reduction in %). */
export function energyChangeLabel(reductionPct: unknown): string {
  const pct = Number(reductionPct);
  if (!Number.isFinite(pct)) return 'unavailable';
  if (pct <= 0) return '0 % (no vector scaled)';
  return `−${pct} %`;
}

export type ToolpathTab = 'kinematics' | 'feedforward';
export const TOOLPATH_TABS: readonly { id: ToolpathTab; label: string }[] = [
  { id: 'kinematics', label: 'Kinematics' },
  { id: 'feedforward', label: 'Feed-forward power' },
];

/** Tab selected by a key press on the tablist (arrows wrap, Home/End jump), or null when the key is not a tab key. */
export function nextToolpathTab(current: ToolpathTab, key: string): ToolpathTab | null {
  const index = TOOLPATH_TABS.findIndex(t => t.id === current);
  const count = TOOLPATH_TABS.length;
  const to = key === 'ArrowRight' ? index + 1 : key === 'ArrowLeft' ? index - 1 : key === 'Home' ? 0 : key === 'End' ? count - 1 : null;
  return to === null ? null : TOOLPATH_TABS[(to + count) % count].id;
}

/** Deep link: `#/toolpath-studio?tab=feedforward` selects the Feed-forward power tab; anything else is Kinematics. */
export function toolpathTabFromHash(hash: string): ToolpathTab {
  const query = hash.replace(/^#\/?/, '').split('?')[1] ?? '';
  const tab = new URLSearchParams(query).get('tab');
  return TOOLPATH_TABS.some(t => t.id === tab) ? (tab as ToolpathTab) : 'kinematics';
}

/** Hash for a tab of the module (Kinematics is the default and carries no query). */
export function toolpathTabHash(tab: ToolpathTab): string {
  return tab === 'feedforward' ? '#/toolpath-studio?tab=feedforward' : '#/toolpath-studio';
}

/** Inputs shared by both tabs (one source of truth in the parent view). */
export interface ToolpathSharedInputs {
  toolpathText: string; setToolpathText: (value: string) => void;
  format: 'gcode' | 'cli'; setFormat: (value: 'gcode' | 'cli') => void;
  defaultPower: number; setDefaultPower: (value: number) => void;
  defaultSpeed: number; setDefaultSpeed: (value: number) => void;
  accelMax: number; setAccelMax: (value: number) => void;
  jumpSpeed: number; setJumpSpeed: (value: number) => void;
  /** False while the tab is hidden: heavy chart content is not rendered then. */
  active?: boolean;
}
