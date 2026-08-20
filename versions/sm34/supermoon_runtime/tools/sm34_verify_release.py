#!/usr/bin/env python3
"""Verify gzip integrity, exact SM33 prefix, and every SM34 embedded file."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re

HEADER = re.compile(rb'^<<<SM34_FILE path="([^"]+)" sha256="([0-9a-f]{64})" bytes="([0-9]+)">>>\n$')
END = b"<<<END_SM34_FILE>>>\n"


def hash_decompressed(path: Path) -> tuple[str, int]:
    result = hashlib.sha256()
    size = 0
    with gzip.open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
            size += len(chunk)
    return result.hexdigest(), size


def hash_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def hash_prefix(path: Path, size: int) -> str:
    result = hashlib.sha256()
    remaining = size
    with path.open("rb") as stream:
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise EOFError("compressed release is shorter than the SM33 member")
            result.update(chunk)
            remaining -= len(chunk)
    return result.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sm33_gzip", type=Path)
    parser.add_argument("prompt_gzip", type=Path)
    parser.add_argument("release", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    base_sha, base_size = hash_decompressed(args.sm33_gzip)
    base_compressed_sha = hash_file(args.sm33_gzip)
    release_prefix_compressed_sha = hash_prefix(args.release, args.sm33_gzip.stat().st_size)
    if release_prefix_compressed_sha != base_compressed_sha:
        raise ValueError("SM33 compressed gzip member changed")
    prefix = hashlib.sha256()
    embedded = 0
    prompt_verified = False
    total = 0
    with gzip.open(args.release, "rb") as stream:
        remaining = base_size
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise EOFError("release is shorter than SM33 prefix")
            prefix.update(chunk)
            remaining -= len(chunk)
            total += len(chunk)
        if prefix.hexdigest() != base_sha:
            raise ValueError("SM33 decompressed prefix changed")
        while line := stream.readline():
            total += len(line)
            match = HEADER.match(line)
            if match is None:
                continue
            name = match.group(1).decode("utf-8")
            expected = match.group(2).decode("ascii")
            size = int(match.group(3))
            payload_hash = hashlib.sha256()
            remaining = size
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise EOFError(f"truncated embedded file {name}")
                payload_hash.update(chunk)
                remaining -= len(chunk)
                total += len(chunk)
            if payload_hash.hexdigest() != expected:
                raise ValueError(f"embedded hash mismatch {name}")
            separator = stream.read(1)
            end = stream.readline()
            total += len(separator) + len(end)
            if separator != b"\n" or end != END:
                raise ValueError(f"invalid framing {name}")
            embedded += 1
            if name == "spec/SUPER_MOON_34_200000_LINE_MASTER_PROMPT.txt.gz":
                prompt_verified = expected == hash_file(args.prompt_gzip)
        if not prompt_verified:
            raise ValueError("embedded master prompt was not verified")
    payload = {
        "format": "SM34_RELEASE_VERIFICATION_V1",
        "status": "PASS",
        "release_name": "SUPER MOON 34 NEW UNIVERSE",
        "sm33_decompressed_prefix_bytes": base_size,
        "sm33_decompressed_prefix_sha256": base_sha,
        "sm33_compressed_prefix_bytes": args.sm33_gzip.stat().st_size,
        "sm33_compressed_prefix_sha256": base_compressed_sha,
        "release_sm33_compressed_prefix_sha256": release_prefix_compressed_sha,
        "sm33_compressed_prefix_verified": True,
        "sm34_embedded_files_verified": embedded,
        "master_prompt_gzip_verified": prompt_verified,
        "release_decompressed_bytes": total,
        "release_compressed_bytes": args.release.stat().st_size,
        "release_sha256": hash_file(args.release),
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
