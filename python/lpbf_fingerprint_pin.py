"""Strict reader for python/lpbf_implementation_fingerprint.expected (design 5c, P1).

One parser shared by test_lpbf_implementation_fingerprint_pin, tools/lpbf_parity_check.py
and tools/lpbf_bump_record.py. Stdlib only; NOT part of IMPLEMENTATION_SOURCE_FILES and
must never be imported by a manifest file.
"""
import re
from pathlib import Path

EXPECTED_FINGERPRINT_FILE = Path(__file__).resolve().parent / "lpbf_implementation_fingerprint.expected"
_PIN = re.compile(rb"([0-9a-f]{64})\r?\n")


def read_pinned_fingerprint(path=EXPECTED_FINGERPRINT_FILE):
    """Return the pinned value; the file must be exactly one lowercase sha256 hex line."""
    match = _PIN.fullmatch(Path(path).read_bytes())
    if match is None:
        raise ValueError(f"{Path(path).name} must contain exactly one lowercase sha256 hex line "
                         "(64 characters, LF or CRLF terminated, nothing else)")
    return match.group(1).decode("ascii")
