#!/usr/bin/env python3
"""Per-process cache of parsed pycalphad databases and compiled equilibrium workspaces.

Why: a pycalphad request spends most of its time building the symbolic phase models and
generating their compiled energy/derivative functions (the GPU audit measured about 55 %
symbolic code generation; 2-10 s on a first call). Those objects depend only on the database
content, the component set and the phase set, not on the composition or temperature values,
so they can be reused across requests in the warm IPC worker processes.

What is cached (both bounded, least recently used entries are evicted first):
  * parsed ``Database`` objects, keyed by the SHA-256 of the TDB text that was parsed
    (the text is read and hashed on every request, so an edited file is never served from a
    stale parse, even when its modification time did not change);
  * pycalphad ``Workspace`` objects, keyed by (pycalphad version, database SHA-256, sorted
    components, sorted phases, condition keys). A Workspace keeps its models and its
    PhaseRecordFactory (the compiled functions); pycalphad itself keeps that factory when only
    condition *values* change (core/workspace.py PRFField.on_dependency_update), which is
    exactly how a cached Workspace is reused.

Invalidation: a database path whose content hash changed drops every entry built from the old
content (counted in ``invalidations``); a different pycalphad version is a different key;
``clear()`` empties everything. Entries are never shared across processes: each IPC worker
process has its own cache, so the first request for a system in a given worker is cold.

Correctness contract (python/test_calphad_model_cache.py): a warm result equals the cold
result exactly (same floating point values), because reuse changes only where the compiled
functions come from, not the calculation.

This module has no pycalphad import at module level: it is imported by calphad_solver on
interpreters without pycalphad too (the locked CI interpreter).
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Hashable, Optional, Tuple

CACHE_SCHEMA_VERSION = 1

# Bounds (number of entries). One COST 507 workspace for a 4-component system holds about
# 50-60 phase models with their compiled functions; the measured resident size is recorded
# in the lane handoff. 0 disables the workspace cache (every request is then built cold).
DEFAULT_MAX_WORKSPACES = 4
DEFAULT_MAX_DATABASES = 4
ENV_MAX_WORKSPACES = "METALLIX_CALPHAD_CACHE_WORKSPACES"
ENV_MAX_DATABASES = "METALLIX_CALPHAD_CACHE_DATABASES"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw.strip() else default
    except ValueError:
        return default
    return max(0, min(64, value))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_tdb_text(path: str) -> str:
    """The TDB text exactly as it is parsed and hashed (one read, so hash and parse agree)."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


class _Entry:
    __slots__ = ("value", "build_ms", "created", "hits", "lock")

    def __init__(self, value: Any, build_ms: float):
        self.value = value
        self.build_ms = build_ms
        self.created = time.time()
        self.hits = 0
        # A Workspace is mutated per request (its conditions are set); one user at a time.
        self.lock = threading.RLock()


class CalphadModelCache:
    """Bounded LRU caches for databases and workspaces of one process."""

    def __init__(self, max_workspaces: Optional[int] = None, max_databases: Optional[int] = None):
        self.max_workspaces = (_env_int(ENV_MAX_WORKSPACES, DEFAULT_MAX_WORKSPACES)
                               if max_workspaces is None else max(0, int(max_workspaces)))
        self.max_databases = (_env_int(ENV_MAX_DATABASES, DEFAULT_MAX_DATABASES)
                              if max_databases is None else max(0, int(max_databases)))
        self._lock = threading.RLock()
        self._databases: "OrderedDict[str, _Entry]" = OrderedDict()
        self._workspaces: "OrderedDict[Hashable, _Entry]" = OrderedDict()
        self._path_sha: Dict[str, str] = {}
        self.requests = 0
        self.workspace_hits = 0
        self.workspace_misses = 0
        self.database_hits = 0
        self.database_misses = 0
        self.evictions = 0
        self.invalidations = 0
        self.created = time.time()

    # ------------------------------------------------------------------ databases
    def database(self, text: str, parse: Callable[[str], Any], path: Optional[str] = None
                 ) -> Tuple[Any, Dict[str, Any]]:
        """Parsed database for ``text`` (parsed with ``parse`` on a miss).

        ``path`` (optional) is the file the text came from; when that path was seen before with
        another hash, every entry built from the old content is dropped first.
        """
        sha = sha256_text(text)
        with self._lock:
            if path is not None:
                key = os.path.normcase(os.path.abspath(path))
                old = self._path_sha.get(key)
                if old is not None and old != sha:
                    self._invalidate_sha(old)
                self._path_sha[key] = sha
            entry = self._databases.get(sha)
            if entry is not None:
                self._databases.move_to_end(sha)
                entry.hits += 1
                self.database_hits += 1
                return entry.value, {"status": "hit", "sha256": sha, "parseMs": 0.0}
        t0 = time.perf_counter()
        dbf = parse(text)
        parse_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        with self._lock:
            self.database_misses += 1
            if self.max_databases > 0:
                self._databases[sha] = _Entry(dbf, parse_ms)
                self._databases.move_to_end(sha)
                while len(self._databases) > self.max_databases:
                    self._databases.popitem(last=False)
                    self.evictions += 1
        return dbf, {"status": "miss", "sha256": sha, "parseMs": parse_ms}

    # ------------------------------------------------------------------ workspaces
    def workspace(self, key: Tuple[Hashable, ...], build: Callable[[], Any]
                  ) -> Tuple[Any, threading.RLock, Dict[str, Any]]:
        """Cached workspace for ``key`` (built with ``build`` on a miss).

        Returns (workspace, lock, info). The caller holds ``lock`` while it sets conditions and
        reads results. ``key[1]`` must be the database SHA-256 (used for invalidation).
        """
        with self._lock:
            self.requests += 1
            entry = self._workspaces.get(key) if self.max_workspaces > 0 else None
            if entry is not None:
                self._workspaces.move_to_end(key)
                entry.hits += 1
                self.workspace_hits += 1
                return entry.value, entry.lock, {"status": "hit", "buildMs": 0.0,
                                                 "originalBuildMs": entry.build_ms,
                                                 "entryHits": entry.hits}
        t0 = time.perf_counter()
        wks = build()
        build_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        new = _Entry(wks, build_ms)
        with self._lock:
            self.workspace_misses += 1
            if self.max_workspaces > 0:
                self._workspaces[key] = new
                self._workspaces.move_to_end(key)
                while len(self._workspaces) > self.max_workspaces:
                    self._workspaces.popitem(last=False)
                    self.evictions += 1
        status = "miss" if self.max_workspaces > 0 else "disabled"
        return wks, new.lock, {"status": status, "buildMs": build_ms, "originalBuildMs": build_ms,
                               "entryHits": 0}

    # ------------------------------------------------------------------ housekeeping
    def _invalidate_sha(self, sha: str) -> None:
        dropped = 0
        if self._databases.pop(sha, None) is not None:
            dropped += 1
        for key in [k for k in self._workspaces if len(k) > 1 and k[1] == sha]:
            del self._workspaces[key]
            dropped += 1
        if dropped:
            self.invalidations += 1

    def clear(self) -> None:
        with self._lock:
            self._databases.clear()
            self._workspaces.clear()
            self._path_sha.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "schemaVersion": CACHE_SCHEMA_VERSION,
                "scope": "process",
                "processId": os.getpid(),
                "workspaceEntries": len(self._workspaces),
                "maxWorkspaceEntries": self.max_workspaces,
                "databaseEntries": len(self._databases),
                "maxDatabaseEntries": self.max_databases,
                "requests": self.requests,
                "workspaceHits": self.workspace_hits,
                "workspaceMisses": self.workspace_misses,
                "databaseHits": self.database_hits,
                "databaseMisses": self.database_misses,
                "evictions": self.evictions,
                "invalidations": self.invalidations,
                "ageSeconds": round(time.time() - self.created, 1),
            }


# One cache per process. calphad_solver runs as __main__ inside the IPC worker (exec of the
# compiled script with a fresh namespace per request), so its own module globals do not
# survive between requests; this module is imported normally and stays in sys.modules.
_PROCESS_CACHE: Optional[CalphadModelCache] = None
_PROCESS_LOCK = threading.Lock()


def process_cache() -> CalphadModelCache:
    global _PROCESS_CACHE
    with _PROCESS_LOCK:
        if _PROCESS_CACHE is None:
            _PROCESS_CACHE = CalphadModelCache()
        return _PROCESS_CACHE


def reset_process_cache(max_workspaces: Optional[int] = None,
                        max_databases: Optional[int] = None) -> CalphadModelCache:
    """Replace the process cache (tests; bounds from the arguments or the environment)."""
    global _PROCESS_CACHE
    with _PROCESS_LOCK:
        _PROCESS_CACHE = CalphadModelCache(max_workspaces, max_databases)
        return _PROCESS_CACHE
