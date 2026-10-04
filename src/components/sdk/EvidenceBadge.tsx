import React from 'react';
import { contractById, type EvidenceType, type OracleState, type RegisteredContract } from '../../modules/registry';

// Phase 7 module SDK: shows a contracted module's evidence ceiling and oracle state from the
// committed contract (src/generated/moduleRegistry.ts). It needs no server, takes no evidence
// input and never derives or upgrades a claim; legacy modules render nothing.

// Labels match the evidence legend in the App header.
const EVIDENCE_LABELS: Record<EvidenceType, string> = {
  measured: 'Measured',
  'validated-simulation': 'Validated simulation',
  'calibrated-simulation': 'Calibrated simulation',
  'literature-estimate': 'Literature estimate',
  'screening-only': 'Screening only',
  unresolved: 'Unresolved',
};

export interface EvidenceBadgeView {
  readonly ceiling: EvidenceType;
  readonly oracle: OracleState;
  readonly text: string;
  readonly title: string;
}

type BadgeContract = Pick<RegisteredContract, 'migrationState' | 'evidence' | 'tests'>;

/** Pure projection of the contract; the ceiling shown is always the contract's own. */
export function evidenceBadgeView(contract: BadgeContract | undefined): EvidenceBadgeView | null {
  if (!contract || contract.migrationState !== 'contracted') return null;
  const ceiling: EvidenceType = contract.evidence.ceiling;
  const { status, ref } = contract.tests.oracle;
  const oracleText = status === 'present'
    ? `Oracle present (${ref}). It checks the numerics only.`
    : 'Oracle pending, so the ceiling stays capped.';
  return {
    ceiling,
    oracle: status,
    text: `Ceiling: ${EVIDENCE_LABELS[ceiling]} · Oracle ${status}`,
    title: `Contract evidence ceiling: the strongest evidence class this module may claim. `
      + `It is not the status of a result and not a validation claim. ${oracleText}`,
  };
}

export function EvidenceBadge({ moduleId }: { readonly moduleId: string }) {
  const view = evidenceBadgeView(contractById(moduleId));
  if (!view) return null;
  return (
    <span title={view.title} data-evidence-ceiling={view.ceiling} data-oracle={view.oracle}
      className="rounded border border-slate-500/60 px-2 py-0.5 text-[11px] text-slate-200">
      {view.text}
    </span>
  );
}
