"""Test support for the Phase 6a old-blob tests (not used by any solver).

Several Phase 6a tests compare the migrated solvers with the pre-migration git
blobs (d33b6f5, 7f3f803). Locally a missing revision (shallow clone, export) skips
those tests. In CI (env CI set, as GitHub Actions does) a missing revision must FAIL
instead, otherwise a shallow checkout would silently turn the evidence off; the
workflow therefore checks out with fetch-depth: 0.
"""

from __future__ import annotations

import os
import unittest
from typing import Callable, Mapping, Optional


def require_git_revision(available: bool, reason: str,
                         env: Optional[Mapping[str, str]] = None) -> Callable[[type], type]:
    """Class decorator: like unittest.skipUnless(available, reason), but with env CI
    set an unavailable revision makes the class fail in setUpClass."""
    if available:
        return lambda cls: cls
    env = os.environ if env is None else env
    if not env.get("CI"):
        return unittest.skip(reason)

    def fail_in_ci(cls: type) -> type:
        def setUpClass(klass):
            raise AssertionError(
                f"{reason}; CI is set, so old-blob tests must not be skipped "
                f"(actions/checkout needs fetch-depth: 0)")
        cls.setUpClass = classmethod(setUpClass)
        return cls

    return fail_in_ci
