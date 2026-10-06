---
paths:
  - "src/**/*.{ts,tsx}"
---

# Frontend rules

- Module registry, workspace membership and maturity labels live in `src/data/workspaces.ts`; lazy views are wired in `src/modules/registry.ts` and `src/modules/views.ts`. Keep existing module IDs and `metallix-navigate-tab` events working. Unknown `#/module-id` hashes must open LPBF.
- Visited modules stay mounted but hidden. Hidden views must pause animation/playback and GPU work and must not render heavy Recharts content.
- The live LPBF process vector is `useMaterialSpecimenStore.activeSpecimen.lpbf`; do not add a second copy.
- Material transfers go through `src/services/materialContextBridge.ts` only. Refuse atomic-percent or unitless composition; never turn a property value into measured evidence.
- `useLpbfBuildJobStore` refuses unknown material identities; never fall back to an IN718 surrogate.
- Research references are explicit evidence links. They must not overwrite solver inputs or auto-apply calibration.
- All user-facing strings are English. Label synthetic/demo data as such; do not label any module Production.
- After a UI change, verify the affected flow in a real browser, including keyboard use and accessibility.
- `src/generated/` and `src/graft/` are generated; `src/UNREACHABLE_SUPPORT_BASELINE*.json` are ratchet baselines, do not loosen them.
