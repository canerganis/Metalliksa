"""Which interpreter runs the real pycalphad equilibria in the test suite.

pycalphad is part of the default runtime, so CALPHAD tests that solve real equilibria are no longer skipped.
They take minutes on a slow runner. In CI they run on the Python 3.12 job only; the Python 3.11 job keeps every
other test as a compatibility check. Locally, and with METALLIX_SLOW_TESTS=1, they always run when pycalphad
is importable. This only selects where tests run; it does not change any solver behaviour.
"""
import os
import sys

import calphad_solver as _cs

_CI_COMPAT_JOB = bool(os.environ.get("CI")) and sys.version_info < (3, 12)
RUN_REAL_SOLVES = _cs.PYCALPHAD_AVAILABLE and (not _CI_COMPAT_JOB or os.environ.get("METALLIX_SLOW_TESTS") == "1")
SKIP_REASON = ("real pycalphad equilibria run on the Python 3.12 CI job and locally; this is the Python 3.11 "
               "compatibility job" if _CI_COMPAT_JOB else "pycalphad is not installed in this interpreter")
