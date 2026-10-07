#!/usr/bin/env python3
"""
Process-window result cache (screening only).

The persistent IPC service executes dispatched scripts freshly on every request, so module-level state
defined inside python/lpbf_process_window.py would be reset each call. This module is *imported* by the
script and therefore lives in sys.modules for the life of the worker process: the LRU below and the
memoised implementation hash persist across requests.

Key = sha256(normalised request + solver revision + implementation hash). A result is only ever served for
an identical normalised request computed by the identical solver revision and implementation closure.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional

MAX_ENTRIES = 16

_LOCK = threading.Lock()
_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_STATS = {"hits": 0, "misses": 0, "evictions": 0}
_IMPL_HASH: Optional[str] = None
_IMPL_HASH_COMPUTATIONS = 0


def implementation_hash() -> str:
    """lpbf_simulation.implementation_fingerprint(), computed once per process (it hashes source files)."""
    global _IMPL_HASH, _IMPL_HASH_COMPUTATIONS
    with _LOCK:
        if _IMPL_HASH is None:
            from lpbf_simulation import implementation_fingerprint
            _IMPL_HASH = str(implementation_fingerprint())
            _IMPL_HASH_COMPUTATIONS += 1
        return _IMPL_HASH


def make_key(normalized_request: Dict[str, Any], solver_revision: str, impl_hash: str) -> str:
    body = json.dumps(
        {"request": normalized_request, "solverRevision": solver_revision, "implementationHash": impl_hash},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def get(key: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            _STATS["misses"] += 1
            return None
        _CACHE.move_to_end(key)
        _STATS["hits"] += 1
        return copy.deepcopy(entry)


def put(key: str, value: Dict[str, Any]) -> None:
    with _LOCK:
        _CACHE[key] = copy.deepcopy(value)
        _CACHE.move_to_end(key)
        while len(_CACHE) > MAX_ENTRIES:
            _CACHE.popitem(last=False)
            _STATS["evictions"] += 1


def clear_results() -> None:
    """Drop cached results and counters; keep the memoised implementation hash."""
    with _LOCK:
        _CACHE.clear()
        _STATS.update(hits=0, misses=0, evictions=0)


def clear() -> None:
    global _IMPL_HASH, _IMPL_HASH_COMPUTATIONS
    clear_results()
    with _LOCK:
        _IMPL_HASH = None
        _IMPL_HASH_COMPUTATIONS = 0


def stats() -> Dict[str, Any]:
    with _LOCK:
        return {"entries": len(_CACHE), "maxEntries": MAX_ENTRIES, **_STATS,
                "implementationHashComputations": _IMPL_HASH_COMPUTATIONS}
