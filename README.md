# Metalliksa | Traceable LPBF Research Workstation

Metalliksa helps LPBF materials and process engineers and research teams inspect process inputs, run bounded analyses, compare results with evidence, and preserve the record needed to reproduce an engineering review.

The product's value hypothesis is that bringing process analysis, materials context, and source-linked findings into one workflow can make technical reviews easier to trace and repeat. Customer demand and measurable operational benefits have not yet been validated.

## Workspaces

- **LPBF Engineering** — define a material and process context, run available thermal and build-screening workflows, and review their inputs, outputs and limitations. LPBF is the primary workflow.
- **Materials Intelligence** — access materials-focused analysis and research tools.
- **Evidence & Qualification** — connect reviewed sources, findings and engineering records, and export a traceable review package.

The Research Hub links literature metadata, reviewed numeric findings and module evidence. Adding a research reference does not silently change solver inputs or establish that a model has been validated.

## Scope and evidence

Metalliksa is a research engineering prototype for research and engineering review. It does not issue production releases, certified material allowables, or standards qualifications. The LPBF transient thermal model is a research solver; numerical checks do not establish experimental validation. Module maturity varies, so check each module's scope and each result's evidence status and limitations before relying on it.

Synthetic demonstrations, literature estimates, measured findings, model results, and software checks are distinct evidence types. A traceable source or successful software check alone does not establish experimental validation.

## Product and venture documents

- [Product overview](docs/PRODUCT_OVERVIEW.md) — intended users, problem and value hypotheses, current scope, maturity, and evidence limits.
- [Product roadmap](ROADMAP.md) — current priorities and evidence gates.
- [Documentation map](docs/README.md) — product and technical documentation.

## Developer setup

For local development, run the server from the repository root:

```bash
npm run dev
```

Optional AI-backed features, including the copilot, micrograph vision and dataset planner, require `OPENAI_API_KEY` on the server. The application interface is in English.

For implementation details, see [workstation architecture and workflows](docs/RESEARCH_WORKSTATION.md) and [LPBF model scope and limitations](docs/LPBF_ENGINEERING.md). Principal checks are `npm run lint`, `npm run test:unit`, `npm run test:lpbf` and `npm run build`; slower LPBF checks are available through `npm run test:lpbf:slow`.

## Contributor handoff

Record each work segment in [the session log](sonkayıtlar/LOG.md): last action, next step, whether the work is complete or partial, and any blocker. Apply this to code, UI, materials, evidence, tests, and documentation.
