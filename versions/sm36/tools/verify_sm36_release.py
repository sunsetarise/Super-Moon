#!/usr/bin/env python3
"""Verify exact SM35 prefix, reconstruct frames, and validate the frame manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest_prefix(path: Path, length: int) -> str:
    sha = hashlib.sha256(); remaining = length
    with path.open("rb") as stream:
        while remaining:
            chunk = stream.read(min(4 * 1024 * 1024, remaining))
            if not chunk: raise ValueError("truncated prefix")
            sha.update(chunk); remaining -= len(chunk)
    return sha.hexdigest()


def file_digest(path: Path) -> tuple[int, str]:
    sha = hashlib.sha256(); total = 0
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            total += len(chunk); sha.update(chunk)
    return total, sha.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release", type=Path)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--reconstruct-tool", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    baseline_size, baseline_sha = file_digest(args.baseline)
    if digest_prefix(args.release, baseline_size) != baseline_sha:
        raise ValueError("compressed SM35 prefix mismatch")
    run = subprocess.run([sys.executable, str(args.reconstruct_tool), str(args.release), "--baseline-compressed-bytes", str(baseline_size), "--output", str(args.scratch)], check=False)
    if run.returncode: raise ValueError("SM36 reconstruction failed")
    manifest_path = args.scratch / "sm36/evidence/SM36_FRAME_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "SM36_FRAME_MANIFEST_V1" or manifest["baseline_sm35"] != {"size_bytes": baseline_size, "sha256": baseline_sha}:
        raise ValueError("frame manifest baseline mismatch")
    for row in manifest["files"]:
        target = args.scratch / row["path"]
        size, sha = file_digest(target)
        if size != row["size_bytes"] or sha != row["sha256"]:
            raise ValueError(f"manifest mismatch: {row['path']}")
    print(f"compressed_prefix_bytes={baseline_size}")
    print(f"compressed_prefix_sha256={baseline_sha}")
    print(f"manifest_files_verified={len(manifest['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
