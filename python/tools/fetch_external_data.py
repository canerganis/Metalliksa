#!/usr/bin/env python3
"""Download and verify the public external datasets listed in
external-data-manifest.json (repo root). No raw data is tracked in git.

    python tools/fetch_external_data.py --verify [--dir DIR]
    python tools/fetch_external_data.py --fetch  [--dir DIR] [--only ID[,ID]]

--verify never touches the network: it checks that each manifest file exists
under DIR with the recorded size and sha256 (entries whose status is not
"downloaded" are reported as skipped, never as passed).
--fetch downloads only manifest URLs over https from allow-listed hosts, writes
into DIR (default: $METALLIKSA_EXTERNAL_DATA or <repo>/external-data, git
ignored), never executes anything, refuses files above the entry's maxBytes and
refuses a sha256 mismatch when the manifest records one. Entries without a
recorded hash print the observed sha256 so the manifest can be updated by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "external-data-manifest.json"
ALLOWED_HOSTS = {"zenodo.org", "www.matcalc.at", "data.nist.gov", "catalog.data.gov"}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def default_dir() -> Path:
    return Path(os.environ.get("METALLIKSA_EXTERNAL_DATA", REPO / "external-data"))


def verify(manifest: dict, base: Path) -> int:
    bad = 0
    for ds in manifest["datasets"]:
        for f in ds["files"]:
            path = base / ds["id"] / f["name"]
            tag = "%s/%s" % (ds["id"], f["name"])
            if f.get("status") != "downloaded":
                print("SKIP  %s (status=%s)" % (tag, f.get("status")))
                continue
            if not path.is_file():
                print("MISSING %s" % tag)
                bad += 1
                continue
            size, digest = path.stat().st_size, sha256_file(path)
            if size != f["sizeBytes"] or digest != f["sha256"]:
                print("MISMATCH %s size=%d sha256=%s" % (tag, size, digest))
                bad += 1
            else:
                print("OK    %s (%d bytes)" % (tag, size))
    return 1 if bad else 0


def fetch(manifest: dict, base: Path, only: set[str] | None) -> int:
    bad = 0
    for ds in manifest["datasets"]:
        if only and ds["id"] not in only:
            continue
        for f in ds["files"]:
            url = f["url"]
            u = urllib.parse.urlparse(url)
            if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS:
                print("REFUSED %s: host/scheme not allow-listed" % url)
                bad += 1
                continue
            dst = base / ds["id"] / f["name"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            cap = f.get("maxBytes", 300 * 1024 * 1024)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "metalliksa-fetch/1"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read(cap + 1)
            except Exception as exc:  # network/HTTP errors are reported, not retried in a loop
                print("FAILED  %s: %s" % (url, exc))
                bad += 1
                continue
            if len(data) > cap:
                print("REFUSED %s: larger than %d bytes" % (url, cap))
                bad += 1
                continue
            digest = hashlib.sha256(data).hexdigest()
            if f.get("sha256") and digest != f["sha256"]:
                print("MISMATCH %s sha256=%s" % (url, digest))
                bad += 1
                continue
            dst.write_bytes(data)
            print("FETCHED %s -> %s (%d bytes, sha256 %s)" % (url, dst, len(data), digest))
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--verify", action="store_true")
    g.add_argument("--fetch", action="store_true")
    ap.add_argument("--dir", type=Path, default=None)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)
    manifest = load_manifest(a.manifest)
    base = a.dir or default_dir()
    if a.verify:
        return verify(manifest, base)
    return fetch(manifest, base, set(filter(None, a.only.split(","))) or None)


if __name__ == "__main__":
    sys.exit(main())
