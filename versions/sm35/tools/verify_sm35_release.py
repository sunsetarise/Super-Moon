#!/usr/bin/env python3
"""Verify compressed/decompressed SM34 prefixes and every SM35 frame."""

from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path
import subprocess
import sys


def prefix_hash(path: Path, length: int) -> str:
    sha = hashlib.sha256(); remaining = length
    with path.open("rb") as stream:
        while remaining:
            chunk = stream.read(min(4 * 1024 * 1024, remaining))
            if not chunk:
                raise ValueError("truncated prefix")
            sha.update(chunk); remaining -= len(chunk)
    return sha.hexdigest()


def decompressed_digest(path: Path) -> tuple[int, str]:
    sha = hashlib.sha256(); total = 0
    with gzip.open(path, "rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            sha.update(chunk); total += len(chunk)
    return total, sha.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release", type=Path)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--reconstruct-tool", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    baseline_size = args.baseline.stat().st_size
    if prefix_hash(args.release, baseline_size) != prefix_hash(args.baseline, baseline_size):
        raise ValueError("compressed SM34 prefix mismatch")
    baseline_decompressed_size, baseline_decompressed_hash = decompressed_digest(args.baseline)
    sha = hashlib.sha256(); remaining = baseline_decompressed_size
    with gzip.open(args.release, "rb") as stream:
        while remaining:
            chunk = stream.read(min(4 * 1024 * 1024, remaining))
            if not chunk:
                raise ValueError("decompressed SM34 prefix truncated")
            sha.update(chunk); remaining -= len(chunk)
    if sha.hexdigest() != baseline_decompressed_hash:
        raise ValueError("decompressed SM34 prefix mismatch")
    run = subprocess.run([sys.executable, str(args.reconstruct_tool), str(args.release), "--baseline-compressed-bytes", str(baseline_size), "--output", str(args.scratch)], check=False)
    if run.returncode:
        raise ValueError("SM35 frame reconstruction failed")
    print(f"compressed_prefix_bytes={baseline_size}")
    print(f"compressed_prefix_sha256={prefix_hash(args.baseline, baseline_size)}")
    print(f"decompressed_prefix_bytes={baseline_decompressed_size}")
    print(f"decompressed_prefix_sha256={baseline_decompressed_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
