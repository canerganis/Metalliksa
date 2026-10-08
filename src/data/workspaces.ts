import { LISTED_CONTRACTS, type ListedModuleId } from '../modules/registry';

/** Product navigation and maturity are separate from the evidence of any result. */
export type ModuleScope = 'Production' | 'Research' | 'Preview' | 'Unresolved';
/** Tooltip of every maturity badge (module header, command palette). */
export const MATURITY_BADGE_TITLE = 'Module maturity; this is not a validation claim for any result.';
export type WorkspaceId = 'lpbf' | 'materials' | 'evidence';
export const WORKSPACES = [
  { id: 'lpbf', label: 'LPBF Engineering', description: 'Process setup, thermal simulation, build screening and specialist process labs.', defaultModule: '3d-distortion-lab' },
  { id: 'materials', label: 'Materials & Characterization', description: 'Material data, thermodynamics, property estimates, characterization and corrosion tools.', defaultModule: 'database' },
  { id: 'evidence', label: 'Evidence & Records', description: 'Sources, measured findings, specimen records and export.', defaultModule: 'research-hub' },
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
/**
 * Module ids that were merged into another module. Old links, bookmarks and the saved last-module state keep
 * working: the id resolves to the target module and, when set, a tab of it. The old id is never a registry id,
 * so the navigation and the command palette (both derived from the registry) never list it.
 */
export const LEGACY_MODULE_REDIRECTS: Readonly<Record<string, { readonly id: ModuleId; readonly tab?: string }>> = {};
function legacyRedirect(value: string): { readonly id: ModuleId; readonly tab?: string } | null {
  return Object.prototype.hasOwnProperty.call(LEGACY_MODULE_REDIRECTS, value) ? LEGACY_MODULE_REDIRECTS[value] : null;
}
/** Hash of the module (with its tab) that a merged module id redirects to, or null when the hash is not a legacy link. */
export function legacyRedirectHash(hash: string): string | null {
  const value = hash.replace(/^#\/?/, '').split(/[?\/]/)[0];
  const target = legacyRedirect(value);
  if (!target) return null;
  return target.tab ? `#/${target.id}?tab=${target.tab}` : `#/${target.id}`;
}
/** Resolves a stored module id (saved last-module state), following a legacy redirect; null when unknown. */
export function resolveModuleId(value: unknown): ModuleId | null {
  if (isModuleId(value)) return value;
  return typeof value === 'string' ? legacyRedirect(value)?.id ?? null : null;
}
export function moduleFromHash(hash: string): ModuleId | null {
  const value = hash.replace(/^#\/?/, '').split(/[?\/]/)[0];
  return resolveModuleId(value);
}
export function moduleHash(id: ModuleId): string { return `#/${id}`; }
