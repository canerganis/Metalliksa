"""Versioned source identity: canonical text identity and historical raw framing.

Only CRLF pairs in registered UTF-8 source files become LF. BOM bytes and lone
CR bytes remain identity-bearing. Unrecognized file extensions remain binary.
Raw-v2 reproduces historical identity only with the historical manifest, source
bytes and solver version; applying it to current files identifies current bytes.
"""
import hashlib
from pathlib import Path, PurePosixPath, PureWindowsPath

RAW_SCHEMA = "lpbf-thermal-implementation-manifest-v2"
CANONICAL_SCHEMA = "lpbf-thermal-implementation-manifest-v3-canonical-utf8-crlf"
TEXT_SUFFIXES = {".py", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx"}
TEXT_PATHS = {"openfoam/Make/files", "openfoam/Make/options"}


def _path(relative):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("Source manifest paths must be canonical relative POSIX strings")
    path = PurePosixPath(relative)
    if (not path.parts or PureWindowsPath(relative).drive or path.is_absolute()
            or ".." in path.parts or path.as_posix() != relative):
        raise ValueError("Source manifest path must stay within its root without aliases")
    return relative


def canonical_source_bytes(relative, content):
    relative = _path(relative)
    if not isinstance(content, bytes):
        raise ValueError("Source manifest contents must be immutable bytes")
    if PurePosixPath(relative).suffix.lower() in TEXT_SUFFIXES or relative in TEXT_PATHS:
        try:
            content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Source file is not strict UTF-8: {relative}") from exc
        return content.replace(b"\r\n", b"\n")
    return content


def _entries(entries):
    result = []
    seen = set()
    for relative, content in entries:
        relative = _path(relative)
        if relative in seen:
            raise ValueError("Implementation source manifest contains duplicate paths")
        if not isinstance(content, bytes):
            raise ValueError("Source manifest contents must be immutable bytes")
        seen.add(relative)
        result.append((relative, content))
    if not result:
        raise ValueError("Implementation source manifest must not be empty")
    return sorted(result)


def fingerprint_manifest_entries(entries, version, *, schema=CANONICAL_SCHEMA):
    if schema not in (RAW_SCHEMA, CANONICAL_SCHEMA):
        raise ValueError("Unsupported source identity schema")
    if not isinstance(version, str) or not version:
        raise ValueError("Source identity version must be a nonempty string")
    digest = hashlib.sha256()
    digest.update((schema+"\0"+version+"\0").encode("utf-8"))
    for relative, raw in _entries(entries):
        content = canonical_source_bytes(relative, raw) if schema == CANONICAL_SCHEMA else raw
        name = relative.encode("utf-8")
        digest.update(len(name).to_bytes(4, "big")); digest.update(name)
        digest.update(len(content).to_bytes(8, "big")); digest.update(content)
    return digest.hexdigest()


def _read_entries(root, source_files):
    root = Path(root).resolve()
    paths = tuple(_path(name) for name in source_files)
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("Implementation source manifest is empty or contains duplicate paths")
    entries = []
    for relative in paths:
        source = (root / relative).resolve()
        if root not in source.parents:
            raise ValueError(f"Implementation source escapes its root: {relative}")
        if not source.is_file():
            raise FileNotFoundError(f"Implementation source is missing from manifest: {relative}")
        entries.append((relative, source.read_bytes()))
    return entries


def fingerprint_sources(root, source_files, version, *, schema=CANONICAL_SCHEMA):
    return fingerprint_manifest_entries(_read_entries(root, source_files), version, schema=schema)


def source_identity(root, source_files, version):
    entries = _entries(_read_entries(root, source_files))
    return {"schema": CANONICAL_SCHEMA, "version": version,
            "implementationHash": fingerprint_manifest_entries(entries, version),
            "rawSchema": RAW_SCHEMA,
            "rawByteImplementationHash": fingerprint_manifest_entries(entries, version, schema=RAW_SCHEMA),
            "manifest": [relative for relative, _ in entries],
            "rawFileSha256": {relative: hashlib.sha256(content).hexdigest() for relative, content in entries},
            "canonicalFileSha256": {relative: hashlib.sha256(canonical_source_bytes(relative, content)).hexdigest()
                                    for relative, content in entries}}
