# Metalliksa documentation map

This directory contains the maintained product and engineering documentation. The generated `graft/` tree is a source snapshot for inspection and is not the documentation authority.

## Start here

- [Project README](../README.md) — setup, commands, and the current product scope.
- [Product overview](PRODUCT_OVERVIEW.md) — product goal, user and customer hypotheses, current scope, and validation needs.
- [Research workstation](RESEARCH_WORKSTATION.md) — workspace structure, shared state, research registry, and evidence boundaries.
- [Scientific research vision](SCIENTIFIC_RESEARCH_VISION.md) — candidate research directions for discriminating LPBF physics hypotheses, discovering model discrepancy, and proposing measurements.
- [LPBF engineering](LPBF_ENGINEERING.md) — thermal model contract, execution modes, verification, and known limitations.
- [UQ evidence](UQ_EVIDENCE.md) — uncertainty-quantification scope and what the worksheets do not establish.
- [Module evidence inventory](MODULE_EVIDENCE_INVENTORY.md) — dated software evidence snapshot; runtime registry and current proof are authoritative for live status.

## Governing project documents

These files live at the repository root because they apply across the whole application:

- [AGENTS.md](../AGENTS.md) — instructions for agents and contributors.
- [RULES.md](../RULES.md) — project governance and validation gates.
- [ROADMAP.md](../ROADMAP.md) — current implementation position and remaining product gaps.
- [SCHEMA.md](archive/SCHEMA.md) — data and API contracts.
- [STANDARDS.md](archive/STANDARDS.md) — standards and qualification reference.
- [PROCESS_PROTOCOLS.md](archive/PROCESS_PROTOCOLS.md) — laboratory and production procedures.
- [GLOSSARY.md](archive/GLOSSARY.md) — terminology.
- [KNOWLEDGE.md](archive/KNOWLEDGE.md) — domain knowledge and reference formulations.

## Evidence and history

- [PROOF.md](../PROOF.md) — dated verification and proof entries. It records what was tested; it is not a release certificate.
- [Session log](../sonkayıtlar/LOG.md) — operational work history, newest entry first.
- [Architecture audit](LPBF_ARCHITECTURE_AUDIT.md) — bounded architecture review.
- [Archived planning documents](archive/README.md) — superseded roadmaps and dated handoffs retained for provenance.

## Authority and maintenance rules

1. Runtime behavior and schemas are authoritative over descriptive prose when they differ.
2. A claim of validation requires a matching entry in `PROOF.md`; a source citation alone is not validation.
3. `PROOF.md` and `sonkayıtlar/LOG.md` are append/prepend records respectively; do not rewrite their history to make it look cleaner.
4. Keep generated source snapshots under `graft/`; do not link to them as user-facing documentation.
5. When a document describes a limitation, keep the limitation visible until the corresponding implementation and evidence exist.
6. Update a canonical document before creating another one for the same purpose. Keep dated protocols, proofs and handoffs only when they preserve reproducibility or an active continuation; do not present them as current product scope.
