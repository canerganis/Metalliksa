# Metalliksa research engineering workstation

Metalliksa's product goal and current validation boundary are summarized in the [product overview](PRODUCT_OVERVIEW.md). This document describes the implemented application structure and workflows; it is not a claim that every workspace or model is production-ready.

## Product structure

The application starts in **LPBF Engineering** on a new browser profile. Returning sessions restore the last module. **Materials Intelligence** contains the existing database, alloy design, CALPHAD, TTT/CCT, thermal cycle, characterization, corrosion and mechanical tools. **Evidence & Qualification** contains Research Hub, measured evidence, Digital Twin, coupon/UQ screening and export. Specialist LPBF labs remain available from the LPBF workspace.

`src/data/workspaces.ts` owns the module registry, workspace membership, conservative maturity labels and suggested next actions. Existing module IDs and `metallix-navigate-tab` events remain supported. Routes use `#/module-id`; browser back/forward restores the selected module. LPBF stage links use `?lpbfStage=...`, and old specialist links remain supported. Unknown module hashes open LPBF safely.

Visited modules remain mounted but hidden during navigation to preserve local input and view state. They are loaded lazily and isolated by a module error boundary. Nested visibility boundaries omit hidden Recharts content while retaining surrounding forms. Thermal viewer and basic slicer animation/playback pause when hidden. Other specialist GPU resources can still remain allocated. Browser reload still resets session-only specialist state.

## Shared LPBF context

- `useMaterialSpecimenStore.activeSpecimen.lpbf` remains the only live P/v/h/t/d/preheat/scan-strategy vector. The slicer reads and writes it directly.
- `materialContextBridge` connects explicit database/pipeline transfers and Alloy Builder changes with the canonical shared profile. It mirrors the canonical material into legacy views at startup without replaying old pipeline data. Atomic-percent or missing-unit transfers are refused instead of being interpreted as weight percent. Composition range midpoints remain labelled nominal estimates; property values are not promoted to measured evidence.
- Material profile IDs derive from exact name, base and sorted composition, so selecting the same profile again retains research associations. Changing chemistry produces a different ID. Physical build and specimen IDs are recorded separately in workflow/evidence context. Existing persisted IDs are not silently rewritten.
- `useLpbfWorkflowStore` persists stage and build/machine/powder/measurement context. Empty entries remain unresolved.
- `useLpbfEngineeringStore` shares advanced inputs, measurement drafts and asynchronous job status. Polling continues without a mounted thermal view. Completed result signatures describe the submitted inputs and expose stale results after edits.
- `useLpbfBuildJobStore` remains the Python analytical screening result owner. Keys include the full defect input, CT threshold, actual mesh identity and UQ sample count. UQ/AM-Bench blocks cannot be attached to a different process. Unknown material identities are refused instead of becoming an IN718 surrogate.
- The qualification dossier exports current and executed inputs separately, numerical checks, source-linked findings and missing evidence. It cannot grant a production release or standards certificate.

The eight stages are Process Setup → Material & Parameters → Thermal Simulation → Melt Pool Analysis → Defect & Regime Screening → Build / Slicer → Experimental Comparison → Qualification Report. A stage change is navigation, not a claim that its engineering work is complete.

## Research and registry contract

`ResearchBrief → ResearchSource → ResearchFinding → ResearchIntegration → ResearchFeedback` is defined in `src/types/research.ts`. Zustand persists records and drafts under `metalliksa-research-registry-v1`. Portable JSON export/import includes schema version, referential checks, conflict detection and non-destructive merge. Storage failure is visible and does not discard the in-memory session.

Source types distinguish primary papers, reviews, standards and technical reports. Findings record a numeric value, explicit unit, interval and uncertainty when reported, material profile, composition, process, machine, parameters, powder condition, heat treatment, method, exact page/table/figure location, evidence kind, confidence, limitations and target module. Unknown fields are not filled with defaults presented as measurements. Different units or conditions block a direct numeric comparison; interval overlap does not establish validation.

Review requires a rationale, source/finding confidence, method, locator, process context, limitations and uncertainty description. Validated/calibrated simulation labels additionally require an experimental reference. Secondary review data cannot be classified as primary measurement evidence. Only measured findings may link to a validation dataset. Conflict flags, source corrections, finding revisions and contradictory feedback withdraw affected module links for renewed review.

Module integration is an explicit **evidence reference**, visible beside the material database, LPBF workspace and experimental register. It never overwrites thermophysical properties or automatically applies calibration. The current numerical extraction is manual: the user reads the original source. PDF/table OCR and automatic SI property-law construction are not implemented.

## Live literature search

`GET /api/research/search?q=...` queries a fixed Crossref upstream for at most 12 metadata records; a DOI query uses the singleton lookup. A query must contain 3–500 characters. The server enforces a 12-second timeout and three concurrent upstream requests, maps unavailable/rate-limited/not-found conditions into controlled JSON responses and refuses outbound lookup in air-gap mode. The manual intake remains available.

The implementation follows the [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) and [query guidance](https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/). Crossref supplies publisher-deposited bibliographic metadata. `journal-article` does not determine primary research versus review; the UI asks the researcher to classify the source. Metadata is not numeric extraction or proof of a claim. Search terms are sent to Crossref when the user runs a search. No API key or full-text access is implied.

## Evidence honesty

Module scope is **Production / Research / Preview / Unresolved**. Current modules are conservatively Research or Preview; no new module is labelled production-ready. Evidence kinds are **Measured / Validated simulation / Calibrated simulation / Literature estimate / Screening only / Unresolved**. These are distinct from source confidence and module scope.

Energy/mass conservation, mesh/timestep convergence and independent experimental validation remain separate. The existing LPBF thermal model does not resolve free surface, momentum, evaporation, recoil, pore trapping or residual stress. Legacy stress/distortion estimates are explicitly screening proxies. See [LPBF engineering model](LPBF_ENGINEERING.md) for the complete model contract and known material/literature gaps.

Fresh digital twins start without inherited measured values or certification. Imported or historical qualification claims are retained as unverified `evidence.reportedClaims` in exports, while effective qualification remains not assessed. Seeded twins and synthetic diffraction patterns are demonstrations. An AI service failure cannot manufacture a successful validation review. MMPDS/coupon tooling retains screening language and does not infer a certified allowable boost from simulated scatter.

## Running and checking

Run `npm run dev` for development. `npm run lint`, `npm run test:unit`, `npm run build`, `npm run test:lpbf`, `npm run test:lpbf:engineering` and `npm run test:meltpool` cover the principal contracts and solvers. With the server running, `npm run test:lpbf:api` exercises live job lifecycle, timeout/cancel, artifacts, calibration and OpenFOAM. The OpenFOAM integration requires its compiled WSL worker; native Python tests explicitly skip that one backend when unavailable.

For a production check, set `NODE_ENV=production` and run `npm start` after building. `PORT` defaults to 3000 and accepts 1–65535. Keep `.lpbf-jobs` and uploaded geometry separate from source commits and export worker artifacts for reproducibility.

Manual browser regression: select an alloy/process, run a thermal job, navigate to another workspace while it runs, return through all eight LPBF stages, inspect stale-input handling and qualification gaps, create a brief, search a DOI, register a source, extract/review/link a finding, inspect its target module, submit feedback, export, reload and verify persisted context. Test unknown routes and empty/error/offline views as well as desktop/mobile layout. Test fixtures must be labelled as synthetic UI checks and must never be presented as experimental evidence.

## Remaining boundaries

This is a local research workstation. Browser persistence and explicit server revisions provide portable JSON backup; there is no authenticated multi-user registry or formal review signature. Linked references do not automatically become executable material laws. Standard qualification still requires applicable physical tests and independent review. Existing physics engines and literature mismatch reports are preserved; this product integration does not create new physical validation.

## Versioned server evidence registry

Research Hub's **Check server** loads the current registry identity and revision. **Save new server revision** sends the browser's evidence snapshot with that expected revision; a changed server returns HTTP 409 and requires another check. Saving is explicit, never triggered by form editing. A timeout may follow a completed write: check before retrying. The client preserves edits made while a save is in flight and does not automatically retry uncertain writes.

When browser and server have diverged, the client loads its last acknowledged historical revision and prepares a three-way comparison. Independent record edits combine only after **Apply reviewed combination to browser**. Conflicting record IDs require an explicit browser/server choice. The full combined snapshot is validated before a single store update; dangling references or asymmetric conflicts block application. Reviews carry over only with their exact finding/source context and all contradictory feedback already present in one trusted input. Ineligible module links are withdrawn and reported. Applying a review fails if browser records changed while it was open. A subsequent save creates a new server revision.

Portable registry exports contain only schema records. Checked and earlier server revisions can be exported without replacing browser work. Transient form drafts remain browser-local and are stripped at server boundaries. If browser persistence detects another tab's write, it pauses instead of overwriting that tab; **Export browser recovery copy** preserves this tab's records and drafts before reload. Import accepts recovery drafts only when they do not conflict with current drafts. This guard also preserves invalid/unreadable original browser storage. Browser tabs are not a live collaborative editor. The localStorage comparison is optimistic, not an atomic cross-process transaction; server compare-and-swap remains the authoritative protection for shared saved revisions.

Local HTTP contract:

- `GET /api/research/registry`: `{ registryId, revision, savedAt, snapshot }`; revision 0 is the empty identity record.
- `PUT /api/research/registry`: `{ registryId, expectedRevision, snapshot }`; returns the new envelope or 409 with the current envelope.
- `GET /api/research/registry/history`: saved revision numbers/timestamps (1 and later).
- `GET /api/research/registry/revisions/:revision`: immutable snapshot envelope, including revision 0.

The registry route mounts its 10 MB JSON parser before the application's larger parser. Schema validation rejects unsupported evidence/review claims and broken references, and canonicalizes schema fields. Browser mutation requests must be same-origin and JSON. These checks are not authentication: everyone with server access can read and write this shared registry. No cloud synchronization or account isolation is claimed.

`RESEARCH_REGISTRY_DIR` selects storage; its default is ignored `.research-registry/` under the server working directory. All server instances must share that directory on a local filesystem supporting atomic hard links. Each revision is flushed to a temporary file and published exclusively under an immutable name while a filesystem lock serializes writers. Normal restart preserves identity and history. Every operation validates the committed revision chain; large histories therefore cost increasing read time. Windows does not expose directory fsync through Node, so power-loss durability is not asserted.

Corrupt/missing revisions, interrupted initialization, inaccessible storage and abandoned `.write-lock` return 503 without resetting data. An operator must verify no writer is active, preserve a backup and inspect files before recovering a lock or damaged chain. The application never auto-deletes a stale lock, repairs history or overwrites a revision. Keep registry data out of Git and back up the configured directory separately from source code.
