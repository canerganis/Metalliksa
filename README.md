# Metalliksa Research Engineering Workstation

Metalliksa is a research engineering platform for materials engineers and researchers working with metal additive manufacturing. It brings LPBF process analysis, materials information, research findings and traceable evidence into one workspace to support engineering review and reproducible investigation.

## Workspaces

- **LPBF Engineering** — define a material and process context, run available thermal and build-screening workflows, and review their inputs, outputs and limitations. LPBF is the primary workflow.
- **Materials Intelligence** — access materials-focused analysis and research tools.
- **Evidence & Qualification** — connect reviewed sources, findings and engineering records, and export a traceable review package.

The Research Hub links literature metadata, reviewed numeric findings and module evidence. Adding a research reference does not silently change solver inputs or establish that a model has been validated.

## Scope and evidence

Metalliksa supports research and engineering review; it does not issue a production release or standards qualification. The LPBF transient thermal model is a research solver, and its results are not automatically experimentally validated. Screening, numerical verification, calibrated simulation and comparison with independent measurements are separate forms of evidence. Check each module's scope and each result's evidence status and limitations before relying on it.

Synthetic demonstrations and literature estimates are distinct from measured findings. A traceable source or successful software check alone does not establish experimental validation.

## Getting started

Run the development server from the repository root:

```bash
npm run dev
```

Optional AI-backed features, including the copilot, micrograph vision and dataset planner, require `OPENAI_API_KEY` on the server. The application interface is in English.
## Documentation and checks

- [Product overview](docs/PRODUCT_OVERVIEW.md) — goal, intended users, current maturity and evidence limits.
- [Documentation map](docs/README.md)
- [Workstation architecture and workflows](docs/RESEARCH_WORKSTATION.md)
- [LPBF model scope and limitations](docs/LPBF_ENGINEERING.md)

Run the principal checks with `npm run lint`, `npm run test:unit`, `npm run test:lpbf` and `npm run build`. The slower LPBF checks are available through `npm run test:lpbf:slow`.
