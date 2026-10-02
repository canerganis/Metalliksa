# Versioned thermal source identity and cache scope

## Source identity

New thermal implementation identities use
`lpbf-thermal-implementation-manifest-v3-canonical-utf8-crlf`.
The reviewed manifest includes the supported thermal production closure and
the identity helper itself. Names, contents, solver version and schema enter
the hash with explicit content lengths and deterministic path ordering.

Known source files are strict UTF-8. Only CRLF pairs become LF; a UTF-8 BOM,
a lone CR, trailing whitespace and every other source byte remain identity
bearing. Supported text suffixes are `.py`, `.c`, `.cc`, `.cpp`, `.cxx`, `.h`,
`.hpp` and `.hxx` (case insensitive), plus `openfoam/Make/files` and
`openfoam/Make/options`. Other extensions remain raw binary bytes. Missing
sources, empty or duplicate manifests, path aliases, drive-qualified paths,
root escapes and invalid text encoding fail closed.

Equal canonical source identity means equal source content under this policy.
It establishes no numerical equivalence across operating systems, libraries,
hardware or runtime environments, and no experimental validation.

```python
from lpbf_simulation import implementation_fingerprint, implementation_source_identity
from lpbf_source_identity import RAW_SCHEMA, fingerprint_sources

canonical_hash = implementation_fingerprint()
inspection = implementation_source_identity()
# Historical verification requires the actual historical root, manifest and version.
historical_raw_hash = fingerprint_sources(
    historical_root, historical_manifest, historical_version, schema=RAW_SCHEMA)
```

`implementation_source_identity()` returns the schema, solver version, sorted
manifest, canonical implementation hash, raw-v2 hash and raw/canonical file
digests from one captured set of bytes. Its raw-v2 hash identifies the current
manifest and current files; it is not an alias for a previous revision.

## Historical records and provenance

Raw-v2 retains the exact historical framing algorithm
`lpbf-thermal-implementation-manifest-v2`. The compatibility fixture is checked
against the saved implementation from before this change. Old reports, fields
and protocol hashes are preserved. No stored record is relabeled or rewritten.
Live source guards continue to reject a frozen protocol after the source changes.
Archive readers compare their recorded historical identities and byte hashes.

New ordinary and queued Torch/Warp results add
`provenance.implementationFingerprintSchema` beside `implementationHash`.
The frontend field is optional for existing records. Absence of this field does
not establish which historical source schema was used. GPU capture hash keys
and artifact contracts retain their existing shapes.

## Cache scope

Ordinary thermal requests use the new
`lpbf-thermal-cache-v2-canonical-production` key: reviewed canonical production
identity, solver version, effective inputs and resolved material. Changing a
manifested production source, material or input invalidates the key. Test,
diagnostic runner and worker source edits do not change this thermal source key.
The worker still adds its existing capability and solver binary evidence.
Changes to orchestration that alter cached output semantics require a deliberate
cache schema revision or another explicit cache dependency.

Requests with any non-null `jobType`, including build jobs and GPU pilots, retain
the exact broad raw cache algorithm over Python and OpenFOAM sources. Their
production closures extend beyond the thermal manifest. The validated pilot
request retains `jobType`; ordinary thermal validation rejects that selector.
Unknown future job selectors take the broad branch as well.

The new thermal schema naturally creates new cache keys. Old cache entries are
preserved, with no database rewrite or destructive cleanup.

## Verification scope

Fixtures cover LF/CRLF parity, source/path/version/material/input invalidation,
excluded file changes, raw-v2 compatibility, strict encoding, path validation,
symlink escape handling and the actual screening result metadata. Existing
worker deduplication, GPU archive, core and historical probe controls are also
checked. The large fixed-event solver experiment is not rerun for this change.

## Recorded result

- Code commit: `3c9385f49a1c26ce0ed0dffabde3e7f48916b838`; local only.
- Production manifest: 37 files, including 34 Python sources and 3 OpenFOAM files.
- Canonical implementation hash: `66c4bc7a9c58dbc0010714c1b246416eaeb9bb50397ad19fc6dcdbe65c78c7e6`.
- Inspection record: `LPBF_SOURCE_IDENTITY_2026-10-02.json`, SHA-256 `aebf1e453588f91a7e7db850afb647a75a9ec7b59712f95b56ca184082b0a81d`.
- Final combined controls: 120 tests, 119 PASS / 1 SKIP / 0 FAIL (36.335 s).
  The Windows symlink test skipped because creation privilege was unavailable.
  The final 20-test identity suite was repeated after two additional path cases:
  19 PASS / 1 SKIP. TypeScript no-emit and Python compilation passed.
- Full-manifest LF/CRLF fixtures and the committed canonical identity matched.
  Raw digests in the inspection record describe the captured working bytes;
  Git newline conversion of legacy sources is covered by canonical comparison.
- 46 nonidentity production functions across the three touched producer files
  retained identical ASTs after removing the added provenance schema field.
  This bounds the code change; it is not a numerical or experimental validation.
- Main graph refresh remains unavailable due a pre-existing denied temporary
  directory. An isolated graph was rebuilt from six byte-exact owned sources.
  Existing user graph edits were preserved.
