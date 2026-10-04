import { LISTED_CONTRACTS, type ListedModuleId } from '../modules/registry';

/** Product navigation and maturity are separate from the evidence of any result. */
export type ModuleScope = 'Production' | 'Research' | 'Preview' | 'Unresolved';
export type WorkspaceId = 'lpbf' | 'materials' | 'evidence' | 'orchestration';
export const WORKSPACES = [
  { id: 'lpbf', label: 'LPBF Engineering', description: 'Process setup through thermal research, build screening and qualification evidence.', defaultModule: '3d-distortion-lab' },
  { id: 'materials', label: 'Materials Intelligence', description: 'Characterization, thermodynamics and material models supporting engineering decisions.', defaultModule: 'database' },
  { id: 'evidence', label: 'Evidence & Qualification', description: 'Sources, experimental records, uncertainty and traceable engineering reports.', defaultModule: 'research-hub' },
  { id: 'orchestration', label: 'AI Orchestration', description: 'Human-gated multi-agent planning for datasets and engineering workflows.', defaultModule: 'ai-orchestrator' },
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
export function isModuleId(value: unknown): value is ModuleId {
  return typeof value === 'string' && MODULES.some(module => module.id === value);
}
export function moduleFromHash(hash: string): ModuleId | null {
  const value = hash.replace(/^#\/?/, '').split(/[?\/]/)[0];
  return isModuleId(value) ? value : null;
}
export function moduleHash(id: ModuleId): string { return `#/${id}`; }
