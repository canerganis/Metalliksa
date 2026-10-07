import { LISTED_CONTRACTS, type ListedModuleId } from '../modules/registry';

/** Product navigation and maturity are separate from the evidence of any result. */
export type ModuleScope = 'Production' | 'Research' | 'Preview' | 'Unresolved';
/** Tooltip of every maturity badge (module header, command palette). */
export const MATURITY_BADGE_TITLE = 'Module maturity; this is not a validation claim for any result.';
export type WorkspaceId = 'lpbf' | 'materials' | 'evidence';
export const WORKSPACES = [
  { id: 'lpbf', label: 'LPBF Engineering', description: 'Process setup, thermal simulation, build screening and specialist process labs.', defaultModule: '3d-distortion-lab' },
  { id: 'materials', label: 'Materials & Characterization', description: 'Material data, thermodynamics, property estimates, characterization and corrosion tools.', defaultModule: 'database' },
  { id: 'evidence', label: 'Evidence & Records', description: 'Sources, measured findings, specimen records, coupon statistics and export.', defaultModule: 'research-hub' },
] as const;

export type ModuleId = ListedModuleId;
export interface NavigationModule {
  readonly id: ModuleId; readonly workspace: WorkspaceId; readonly label: string;
  readonly scope: ModuleScope; readonly description: string; readonly next: string;
}

/**
 * Navigation entries derived from the module registry (src/generated/moduleRegistry.ts, emitted by
 * python/module_registry.py): every `listed` contract in registry order. `scope` is the contract
 * maturity. tests/workspaces-registry-parity.test.ts pins this list to the hand-written golden.
 */
export const MODULES: readonly NavigationModule[] = LISTED_CONTRACTS.map(contract => ({
  id: contract.id, workspace: contract.workspace, label: contract.label,
  scope: contract.maturity, description: contract.description, next: contract.next,
}));

/** The flagship LPBF screening flow, in flow order. Labels always come from the registry (MODULES). */
export const CORE_MODULE_IDS: readonly ModuleId[] = ['3d-distortion-lab', 'lpbf-optimizer', 'lpbf-dataset-comparison', 'lpbf-calibration-scorecard'];
export const CORE_FLOW: readonly { readonly id: ModuleId; readonly verb: string }[] = [
  { id: '3d-distortion-lab', verb: 'Set up and run' },
  { id: 'lpbf-optimizer', verb: 'Screen the process window' },
  { id: 'lpbf-dataset-comparison', verb: 'Compare with published data' },
  { id: 'lpbf-calibration-scorecard', verb: 'Check the scorecard' },
];
export function isCoreModule(id: string): boolean { return CORE_MODULE_IDS.some(core => core === id); }
/** Every listed module that is not part of the core flow (shown under "Labs"). Registry order. */
export const LAB_MODULES: readonly NavigationModule[] = MODULES.filter(module => !isCoreModule(module.id));
export function isModuleId(value: unknown): value is ModuleId {
  return typeof value === 'string' && MODULES.some(module => module.id === value);
}
export function moduleFromHash(hash: string): ModuleId | null {
  const value = hash.replace(/^#\/?/, '').split(/[?\/]/)[0];
  return isModuleId(value) ? value : null;
}
export function moduleHash(id: ModuleId): string { return `#/${id}`; }
