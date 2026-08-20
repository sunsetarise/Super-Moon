#!/usr/bin/env python3
"""Verify every split part and the concatenated byte stream without reassembly."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = args.manifest.parent
    combined = hashlib.sha256()
    total = 0
    for record in payload["parts"]:
        path = root / record["file"]
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
                combined.update(chunk)
                size += len(chunk)
                total += len(chunk)
        if size != record["bytes"] or digest.hexdigest() != record["sha256"]:
            raise SystemExit(f"part verification failed: {path.name}")
    if total != payload["source_bytes"] or combined.hexdigest() != payload["source_sha256"]:
        raise SystemExit("combined stream verification failed")
    print(f"parts=PASS count={len(payload['parts'])} bytes={total} sha256={combined.hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
