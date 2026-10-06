import React from "react";
import { describeLpbfDefault, type LpbfSpecimenState } from "../store/useMaterialSpecimenStore";

/**
 * Discloses LPBF inputs that are unsourced defaults or class heuristics (see LpbfSpecimenState.defaultsApplied), each
 * with the value in use. Renders nothing when no field is flagged.
 */
export function LpbfDefaultsNote({ lpbf, className }: { lpbf: LpbfSpecimenState; className?: string }) {
  const flagged = lpbf.defaultsApplied ?? [];
  if (!flagged.length) return null;
  return (
    <span role="note" data-testid="lpbf-defaults-applied" className={className ?? "text-amber-300"}>
      Unsourced defaults or class heuristics in use: {flagged.map(key => describeLpbfDefault(key, lpbf)).join("; ")}
    </span>
  );
}
